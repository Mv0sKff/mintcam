from flask import Flask, Response, render_template, request, jsonify, send_file
import cv2
import numpy as np
import yaml
import os
import subprocess
from datetime import datetime
import threading
import time

# Load configuration
def load_config():
    try:
        with open('config.yml', 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {'name': 'mintcam'}  # Default fallback

config = load_config()

# Set DEBUG_MODE to True for testing without Picamera2
DEBUG_MODE = bool(config.get("debug_mode", True))
# Generate more useful demo images for demo
DEMO_LIVE_VIDEO = False

if not DEBUG_MODE:
    from picamera2 import Picamera2

# Initialize Flask app
app = Flask(__name__)

# Current camera settings
camera_settings = {
    'width': 640,
    'height': 480,
    'fps': 30,
    'hdr': False
}

# Video recording state
video_recording = {
    'is_recording': False,
    'output_path': None,
    'recorder': None
}

# Resolution presets
resolution_presets = {
    '640x480x30': {'width': 640, 'height': 480, 'fps': 30, 'hdr': False},
    '1536x864x30': {'width': 1536, 'height': 864, 'fps': 30, 'hdr': False},
    '2304x1296x30': {'width': 2304, 'height': 1296, 'fps': 30, 'hdr': False},
    '4608x2592x30': {'width': 4608, 'height': 2592, 'fps': 30, 'hdr': False},
}

if not DEBUG_MODE:
    # Initialize Picamera2
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
    )
    picam2.configure(config)
    picam2.start()

# Generator for MJPEG stream
def gen_frames():
    global camera_settings
    while True:
        if DEBUG_MODE:
            # Create a synthetic frame with current resolution
            width, height = camera_settings['width'], camera_settings['height']
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            if DEMO_LIVE_VIDEO:
                settings_text = f"{width}x{height} {camera_settings['fps']}fps"
                if camera_settings['hdr']:
                    settings_text += " HDR"
                cv2.putText(frame, 'DEBUG MODE', (width//10, height//2),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                cv2.putText(frame, settings_text, (width//10, height//2 + 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                bgr = frame  # Already in BGR format
                bgr = np.zeros((height, width, 3), dtype=np.uint8)
            bgr = frame
        else:
            # Capture frame from camera
            frame = picam2.capture_array('main')
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Encode frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', bgr)
        if not ret:
            continue
        frame_bytes = jpeg.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/live_video_feed')
def live_video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return render_template('index.html', config=config)

@app.route('/set_resolution', methods=['POST'])
def set_resolution():
    global camera_settings

    resolution_key = request.form.get('resolution', '640x480x30')

    if resolution_key in resolution_presets:
        new_settings = resolution_presets[resolution_key]
        camera_settings = new_settings

        if not DEBUG_MODE:
            # Reconfigure the camera with new settings
            picam2.stop()
            config = picam2.create_video_configuration(
                main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
            )
            # Configure HDR if needed
            #if camera_settings['hdr']:
            #    picam2.set_controls({"HighDynamicRangeMode": 1})
            #else:
            #    picam2.set_controls({"HighDynamicRangeMode": 0})

            # Set framerate
            picam2.set_controls({"FrameRate": camera_settings['fps']})

            picam2.configure(config)
            picam2.start()

    return jsonify({'success': True, 'settings': camera_settings})

@app.route('/take_picture', methods=['POST'])
def take_picture():
    try:
        # Create pictures directory if it doesn't exist
        pictures_dir = 'pictures'
        if not os.path.exists(pictures_dir):
            os.makedirs(pictures_dir)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'picture_{timestamp}.jpg'
        filepath = os.path.join(pictures_dir, filename)

        if DEBUG_MODE:
            # Create a synthetic image for debug mode
            width, height = camera_settings['width'], camera_settings['height']
            bgr = np.zeros((height, width, 3), dtype=np.uint8)
            # Add some visual content to the debug image
            cv2.putText(bgr, f'Debug Image {timestamp}', (50, height//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        else:
            # Capture a high-quality still image from camera
            frame = picam2.capture_array('main')
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Save the image
        success = cv2.imwrite(filepath, bgr)

        if success:
            return jsonify({
                'success': True,
                'message': 'Picture taken successfully',
                'filename': filename,
                'filepath': filepath
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to save picture'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error taking picture: {str(e)}'
        }), 500

@app.route('/pictures', methods=['GET'])
def list_pictures():
    try:
        pictures_dir = 'pictures'
        if not os.path.exists(pictures_dir):
            return jsonify({'success': True, 'pictures': []})

        pictures = []
        for filename in os.listdir(pictures_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(pictures_dir, filename)
                stat = os.stat(filepath)
                pictures.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        # Sort by creation time, newest first
        pictures.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({
            'success': True,
            'pictures': pictures,
            'count': len(pictures)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing pictures: {str(e)}'
        }), 500

@app.route('/pictures/<filename>')
def serve_picture(filename):
    try:
        pictures_dir = 'pictures'
        filepath = os.path.join(pictures_dir, filename)

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Picture not found'
            }), 404

        return send_file(filepath, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error serving picture: {str(e)}'
        }), 500

@app.route('/record_video', methods=['POST'])
def record_video():
    global video_recording

    try:
        data = request.get_json() or {}
        duration = min(int(data.get('duration', 30)), 30)  # Max 30 seconds

        if video_recording['is_recording']:
            return jsonify({
                'success': False,
                'message': 'Video recording already in progress'
            }), 400

        # Create videos directory if it doesn't exist
        videos_dir = 'videos'
        if not os.path.exists(videos_dir):
            os.makedirs(videos_dir)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'video_{timestamp}.mp4'
        filepath = os.path.join(videos_dir, filename)

        if DEBUG_MODE:
            # Create a synthetic video for debug mode
            width, height = camera_settings['width'], camera_settings['height']

            # Use ffmpeg to create a test video
            import subprocess
            ffmpeg_cmd = [
                'ffmpeg', '-f', 'lavfi', '-i',
                f'testsrc=duration={duration}:size={width}x{height}:rate={camera_settings["fps"]}',
                '-pix_fmt', 'yuv420p', '-y', filepath
            ]

            video_recording['is_recording'] = True
            video_recording['output_path'] = filepath

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

            video_recording['is_recording'] = False
            video_recording['output_path'] = None

            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': f'Video recorded successfully ({duration}s)',
                    'filename': filename,
                    'filepath': filepath,
                    'duration': duration
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Failed to create test video: {result.stderr}'
                }), 500
        else:
            # Record video using picamera2
            video_recording['is_recording'] = True
            video_recording['output_path'] = filepath

            # Stop the current video stream temporarily
            picam2.stop()

            # Configure for video recording
            video_config = picam2.create_video_configuration(
                main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])},
                controls={'FrameRate': camera_settings['fps']}
            )
            picam2.configure(video_config)

            # Start recording
            encoder = picam2.start_recording(filepath, format='mp4')

            # Record for the specified duration
            time.sleep(duration)

            # Stop recording
            picam2.stop_recording()

            # Restart the video stream
            stream_config = picam2.create_video_configuration(
                main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
            )
            picam2.configure(stream_config)
            picam2.start()

            video_recording['is_recording'] = False
            video_recording['output_path'] = None

            return jsonify({
                'success': True,
                'message': f'Video recorded successfully ({duration}s)',
                'filename': filename,
                'filepath': filepath,
                'duration': duration
            })

    except Exception as e:
        video_recording['is_recording'] = False
        video_recording['output_path'] = None
        return jsonify({
            'success': False,
            'message': f'Error recording video: {str(e)}'
        }), 500

@app.route('/videos', methods=['GET'])
def list_videos():
    try:
        videos_dir = 'videos'
        if not os.path.exists(videos_dir):
            return jsonify({'success': True, 'videos': []})

        videos = []
        for filename in os.listdir(videos_dir):
            if filename.lower().endswith(('.mp4', '.avi', '.mov')):
                filepath = os.path.join(videos_dir, filename)
                stat = os.stat(filepath)
                videos.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        # Sort by creation time, newest first
        videos.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({
            'success': True,
            'videos': videos,
            'count': len(videos)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing videos: {str(e)}'
        }), 500

@app.route('/videos/<filename>')
def serve_video(filename):
    try:
        videos_dir = 'videos'
        filepath = os.path.join(videos_dir, filename)

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Video not found'
            }), 404

        return send_file(filepath, mimetype='video/mp4')

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error serving video: {str(e)}'
        }), 500

@app.route('/create_recorder', methods=['POST'])
def create_recorder():
    try:
        data = request.get_json()
        hour = data.get('hour')
        minute = data.get('minute')
        record_type = data.get('record_type', 'picture')  # 'picture' or 'video'
        duration = data.get('duration', 30) if record_type == 'video' else None
        name = data.get('name', 'recorder')

        if hour is None or minute is None:
            return jsonify({
                'success': False,
                'message': 'Hour and minute are required'
            }), 400

        # Call schedule.py script with record type and duration
        cmd_args = ['python3', 'schedule.py', str(hour), str(minute), record_type]
        if record_type == 'video' and duration:
            cmd_args.append(str(min(int(duration), 30)))  # Max 30 seconds

        result = subprocess.run(cmd_args, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Recorder "{name}" scheduled successfully',
                'hour': hour,
                'minute': minute,
                'cron_output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to schedule recorder: {result.stderr}'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating recorder: {str(e)}'
        }), 500

@app.route('/delete_recorder', methods=['POST'])
def delete_recorder():
    try:
        data = request.get_json()
        hour = data.get('hour')
        minute = data.get('minute')

        if hour is None or minute is None:
            return jsonify({
                'success': False,
                'message': 'Hour and minute are required'
            }), 400

        # Find and delete the recorder with matching hour and minute
        # We need to get the full comment first since it may include type and duration
        cron_result = subprocess.run([
            'crontab', '-l'
        ], capture_output=True, text=True)

        matching_comment = None
        if cron_result.returncode == 0:
            lines = cron_result.stdout.strip().split('\n')
            for line in lines:
                if f'recorder h={hour} m={minute}' in line and 'callback.py' in line:
                    comment_start = line.find('#')
                    if comment_start != -1:
                        matching_comment = line[comment_start + 1:].strip()
                        break

        if not matching_comment:
            return jsonify({
                'success': False,
                'message': 'Recorder not found'
            }), 404

        # Call unschedule.py script with the full matching comment
        result = subprocess.run([
            'python3', 'unschedule.py', matching_comment
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Recorder deleted successfully',
                'unschedule_output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to delete recorder: {result.stderr}'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting recorder: {str(e)}'
        }), 500

@app.route('/list_recorders', methods=['GET'])
def list_recorders():
    try:
        # Get current user's crontab
        result = subprocess.run([
            'crontab', '-l'
        ], capture_output=True, text=True)

        recorders = []
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'recorder h=' in line and 'callback.py' in line:
                    # Parse the comment to extract hour, minute, and recording details
                    comment_start = line.find('#')
                    if comment_start != -1:
                        comment = line[comment_start + 1:].strip()
                        # Extract h=, m=, type=, and duration= values
                        import re
                        h_match = re.search(r'h=(\d+)', comment)
                        m_match = re.search(r'm=(\d+)', comment)
                        type_match = re.search(r'type=(\w+)', comment)
                        duration_match = re.search(r'duration=(\d+)', comment)

                        if h_match and m_match:
                            hour = int(h_match.group(1))
                            minute = int(m_match.group(1))
                            record_type = type_match.group(1) if type_match else 'picture'
                            duration = int(duration_match.group(1)) if duration_match else None

                            cron_parts = line.split('#')[0].strip().split()
                            if len(cron_parts) >= 5:
                                recorder_data = {
                                    'hour': hour,
                                    'minute': minute,
                                    'record_type': record_type,
                                    'cron_expression': ' '.join(cron_parts[:5]),
                                    'comment': comment
                                }
                                if duration:
                                    recorder_data['duration'] = duration
                                recorders.append(recorder_data)

        return jsonify({
            'success': True,
            'recorders': recorders
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing recorders: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(config.get("port", 5000)), debug=DEBUG_MODE)
