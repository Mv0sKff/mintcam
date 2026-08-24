from flask import Flask, Response, render_template, request, jsonify, send_file
import cv2
import numpy as np
import yaml
import os
import sys
import subprocess
from datetime import datetime
import threading
import time
import io
import shutil
from PIL import Image

# Paths: this file lives in <repo>/scanner/webapp.py
SCANNER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCANNER_DIR)
CONFIG_PATH = os.path.join(REPO_ROOT, 'config.yml')
RECORDINGS_DIR = os.path.join(SCANNER_DIR, 'recordings')
OUTPUT_DIR = os.path.join(SCANNER_DIR, 'output')

# Load configuration
def load_config():
    try:
        with open(CONFIG_PATH, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {'name': 'mintcam'}  # Default fallback

config = load_config()

# Set DEBUG_MODE to True for testing without Picamera2
DEBUG_MODE = bool(config.get("debug_mode", True))

if not DEBUG_MODE:
    from picamera2 import Picamera2

# Initialize Flask app (templates/static default to scanner/templates, scanner/static)
app = Flask(__name__)

# Camera settings (fixed for scanner; matches app.py defaults)
camera_settings = {
    'width': 640,
    'height': 480,
    'fps': 30,
    'hdr': False
}

# Recording state (non-blocking, threaded)
recording_state = {
    'is_recording': False,
    'filename': None,
    'filepath': None,
    'writer': None,
    'stop_event': None,
    'thread': None,
    'error': None
}

# Stitch job state
stitch_job = {
    'status': 'idle',  # idle | running | done | failed
    'input': None,
    'output': None,
    'error': None,
    'started': None,
    'finished': None
}

if not DEBUG_MODE:
    # Initialize Picamera2
    picam2 = Picamera2()
    picam_config = picam2.create_video_configuration(
        main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
    )
    picam2.configure(picam_config)
    picam2.start()

# Generator for MJPEG stream
def gen_frames():
    while True:
        if DEBUG_MODE:
            # Create a synthetic frame with current resolution
            width, height = camera_settings['width'], camera_settings['height']
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.putText(frame, 'SCANNER DEBUG MODE', (width//10, height//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            timestamp = datetime.now().strftime('%H:%M:%S')
            cv2.putText(frame, timestamp, (width//10, height//2 + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            img = Image.fromarray(frame, 'RGB')
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            frame_bytes = img_buffer.getvalue()
        else:
            frame = picam2.capture_array('main')
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb, 'RGB')
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            frame_bytes = img_buffer.getvalue()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/live_video_feed')
def live_video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return render_template('index.html', config=config)


def _record_debug(stop_event, filepath):
    """Debug-mode recording: write synthetic frames until stop_event is set."""
    width, height = camera_settings['width'], camera_settings['height']
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filepath, fourcc, camera_settings['fps'], (width, height))
    recording_state['writer'] = out
    frame_num = 0
    try:
        while not stop_event.is_set():
            frame = np.full((height, width, 3), (255, 0, 0), dtype=np.uint8)
            cv2.putText(frame, 'SCANNER DEBUG MODE', (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame, f'Frame: {frame_num}', (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            out.write(frame)
            frame_num += 1
            time.sleep(1.0 / camera_settings['fps'])
    except Exception as e:
        recording_state['error'] = str(e)
    finally:
        try:
            out.release()
        except Exception:
            pass
        recording_state['is_recording'] = False


def _record_nondebug(stop_event, filepath, h264_filepath):
    """Non-debug recording: picam2 H264 until stop_event, then ffmpeg convert."""
    try:
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import FileOutput

        # Stop the current video stream temporarily
        picam2.stop()

        video_config = picam2.create_video_configuration(
            main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
        )
        picam2.configure(video_config)

        encoder = H264Encoder()
        output = FileOutput(h264_filepath)
        picam2.start_recording(encoder, output)

        while not stop_event.is_set():
            time.sleep(0.1)

        picam2.stop_recording()

        # Convert H264 to MP4 using ffmpeg
        convert_success = False
        if shutil.which('ffmpeg'):
            try:
                ffmpeg_cmd = [
                    'ffmpeg', '-i', h264_filepath, '-c', 'copy',
                    '-f', 'mp4', '-y', filepath
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    convert_success = True
                    os.remove(h264_filepath)
                else:
                    print(f"FFmpeg conversion failed: {result.stderr}")
            except Exception as ffmpeg_error:
                print(f"FFmpeg failed: {ffmpeg_error}")
        else:
            print("FFmpeg not found in PATH")

        if not convert_success and os.path.exists(h264_filepath):
            os.rename(h264_filepath, filepath)
            print(f"Video saved as H264 format: {filepath}")
    except Exception as e:
        recording_state['error'] = str(e)
    finally:
        # Restart the video stream for live feed
        if not DEBUG_MODE:
            try:
                stream_config = picam2.create_video_configuration(
                    main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
                )
                picam2.configure(stream_config)
                picam2.start()
            except Exception as stream_error:
                print(f"Failed to restart video stream: {stream_error}")
        recording_state['is_recording'] = False


@app.route('/start_recording', methods=['POST'])
def start_recording():
    if recording_state['is_recording']:
        return jsonify({
            'success': False,
            'message': 'Recording already in progress'
        }), 400

    try:
        os.makedirs(RECORDINGS_DIR, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'scan_{timestamp}.mp4'
        filepath = os.path.join(RECORDINGS_DIR, filename)

        stop_event = threading.Event()
        recording_state['is_recording'] = True
        recording_state['filename'] = filename
        recording_state['filepath'] = filepath
        recording_state['stop_event'] = stop_event
        recording_state['error'] = None
        recording_state['writer'] = None

        if DEBUG_MODE:
            thread = threading.Thread(target=_record_debug, args=(stop_event, filepath), daemon=True)
        else:
            h264_filepath = filepath.replace('.mp4', '.h264')
            thread = threading.Thread(target=_record_nondebug, args=(stop_event, filepath, h264_filepath), daemon=True)

        recording_state['thread'] = thread
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Recording started',
            'filename': filename
        })

    except Exception as e:
        recording_state['is_recording'] = False
        return jsonify({
            'success': False,
            'message': f'Error starting recording: {str(e)}'
        }), 500


@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    if not recording_state['is_recording']:
        return jsonify({
            'success': False,
            'message': 'No recording in progress'
        }), 400

    try:
        stop_event = recording_state.get('stop_event')
        if stop_event:
            stop_event.set()

        thread = recording_state.get('thread')
        if thread:
            thread.join(timeout=15)

        filename = recording_state.get('filename')
        filepath = recording_state.get('filepath')
        error = recording_state.get('error')

        recording_state['is_recording'] = False
        recording_state['thread'] = None
        recording_state['stop_event'] = None
        recording_state['writer'] = None

        if error:
            return jsonify({
                'success': False,
                'message': f'Recording stopped with error: {error}',
                'filename': filename
            }), 500

        if not filepath or not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Recording stopped but no video file was created'
            }), 500

        return jsonify({
            'success': True,
            'message': 'Recording stopped',
            'filename': filename,
            'filepath': filepath
        })

    except Exception as e:
        recording_state['is_recording'] = False
        return jsonify({
            'success': False,
            'message': f'Error stopping recording: {str(e)}'
        }), 500


def _run_stitch(video_path, output_path):
    """Background stitch job: subprocess for isolation, cwd=repo root."""
    stitch_job['status'] = 'running'
    stitch_job['error'] = None
    try:
        # Use the same interpreter as this process (respects the active venv)
        cmd = [
            sys.executable, '-m', 'scanner.stitch', video_path,
            '-o', output_path, '-v'
        ]
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(output_path):
            stitch_job['status'] = 'done'
            stitch_job['output'] = output_path
        else:
            stitch_job['status'] = 'failed'
            stitch_job['error'] = (result.stderr or result.stdout or 'stitch failed').strip()[-2000:]
    except Exception as e:
        stitch_job['status'] = 'failed'
        stitch_job['error'] = str(e)
    finally:
        stitch_job['finished'] = datetime.now().isoformat()


@app.route('/stitch', methods=['POST'])
def stitch():
    if stitch_job['status'] == 'running':
        return jsonify({
            'success': False,
            'message': 'A stitch job is already running'
        }), 400

    data = request.get_json() or {}
    filename = data.get('filename', '')

    # Security: prevent path traversal
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({
            'success': False,
            'message': 'Invalid filename'
        }), 400

    video_path = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(video_path):
        return jsonify({
            'success': False,
            'message': f'Recording not found: {filename}'
        }), 404

    # Lazy check: stitch module must exist (created by another agent)
    stitch_module = os.path.join(SCANNER_DIR, 'stitch.py')
    if not os.path.exists(stitch_module):
        return jsonify({
            'success': False,
            'message': 'Stitch module not available yet (scanner/stitch.py missing)'
        }), 500

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_name = os.path.splitext(filename)[0] + '.jpg'
    output_path = os.path.join(OUTPUT_DIR, output_name)

    stitch_job['input'] = video_path
    stitch_job['output'] = output_path
    stitch_job['started'] = datetime.now().isoformat()
    stitch_job['finished'] = None
    stitch_job['error'] = None

    thread = threading.Thread(target=_run_stitch, args=(video_path, output_path), daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'message': 'Stitch job started',
        'output': output_name
    })


@app.route('/stitch_status', methods=['GET'])
def stitch_status():
    return jsonify({
        'success': True,
        'job': {
            'status': stitch_job['status'],
            'input': os.path.basename(stitch_job['input']) if stitch_job['input'] else None,
            'output': os.path.basename(stitch_job['output']) if stitch_job['output'] else None,
            'error': stitch_job['error'],
            'started': stitch_job['started'],
            'finished': stitch_job['finished']
        }
    })


@app.route('/scans', methods=['GET'])
def list_scans():
    try:
        if not os.path.exists(OUTPUT_DIR):
            return jsonify({'success': True, 'scans': []})

        scans = []
        for filename in os.listdir(OUTPUT_DIR):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(OUTPUT_DIR, filename)
                stat = os.stat(filepath)
                scans.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        scans.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({
            'success': True,
            'scans': scans,
            'count': len(scans)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing scans: {str(e)}'
        }), 500


@app.route('/scans/<filename>')
def serve_scan(filename):
    try:
        # Security: prevent path traversal attacks
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid filename'
            }), 400

        filepath = os.path.join(OUTPUT_DIR, filename)

        # Security: ensure file is actually in the output directory
        if not os.path.commonpath([os.path.abspath(OUTPUT_DIR), os.path.abspath(filepath)]) == os.path.abspath(OUTPUT_DIR):
            return jsonify({
                'success': False,
                'message': 'Invalid file path'
            }), 400

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Scan not found'
            }), 404

        return send_file(filepath, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error serving scan: {str(e)}'
        }), 500


@app.route('/latest_scan', methods=['GET'])
def latest_scan():
    try:
        if not os.path.exists(OUTPUT_DIR):
            return jsonify({
                'success': False,
                'message': 'No scans available yet'
            }), 404

        candidates = [
            f for f in os.listdir(OUTPUT_DIR)
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ]
        if not candidates:
            return jsonify({
                'success': False,
                'message': 'No scans available yet'
            }), 404

        newest = max(candidates, key=lambda f: os.path.getctime(os.path.join(OUTPUT_DIR, f)))
        filepath = os.path.join(OUTPUT_DIR, newest)
        return send_file(filepath, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error serving latest scan: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(config.get('scanner_port', 5000)), debug=DEBUG_MODE)
