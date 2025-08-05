from flask import Flask, Response, render_template, request, jsonify, send_file
import cv2
import numpy as np
import yaml
import os
import subprocess
from datetime import datetime

# Set DEBUG_MODE to True for testing without Picamera2
DEBUG_MODE = True
# Generate more useful demo images for demo
DEMO_LIVE_VIDEO = False

if not DEBUG_MODE:
    from picamera2 import Picamera2

# Load configuration
def load_config():
    try:
        with open('config.yml', 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {'name': 'mintcam'}  # Default fallback

config = load_config()

# Initialize Flask app
app = Flask(__name__)

# Current camera settings
camera_settings = {
    'width': 640,
    'height': 480,
    'fps': 30,
    'hdr': False
}

# Resolution presets
resolution_presets = {
    '2304x1296x56': {'width': 2304, 'height': 1296, 'fps': 56, 'hdr': False},
    '2304x1296x30xHDR': {'width': 2304, 'height': 1296, 'fps': 30, 'hdr': True},
    '1536x864x120': {'width': 1536, 'height': 864, 'fps': 120, 'hdr': False},
    '640x480x30': {'width': 640, 'height': 480, 'fps': 30, 'hdr': False}
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
            if camera_settings['hdr']:
                picam2.set_controls({"HighDynamicRangeMode": 1})
            else:
                picam2.set_controls({"HighDynamicRangeMode": 0})

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

@app.route('/create_recorder', methods=['POST'])
def create_recorder():
    try:
        data = request.get_json()
        hour = data.get('hour')
        minute = data.get('minute')
        name = data.get('name', 'recorder')

        if hour is None or minute is None:
            return jsonify({
                'success': False,
                'message': 'Hour and minute are required'
            }), 400

        # Call schedule.py script
        result = subprocess.run([
            'python3', 'schedule.py', str(hour), str(minute)
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))

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

        # Create comment to match the one in schedule.py
        comment = f'recorder h={hour} m={minute}'

        # Call unschedule.py script
        result = subprocess.run([
            'python3', 'unschedule.py', comment
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
                    # Parse the comment to extract hour and minute
                    comment_start = line.find('#')
                    if comment_start != -1:
                        comment = line[comment_start + 1:].strip()
                        # Extract h= and m= values
                        import re
                        h_match = re.search(r'h=(\d+)', comment)
                        m_match = re.search(r'm=(\d+)', comment)
                        if h_match and m_match:
                            hour = int(h_match.group(1))
                            minute = int(m_match.group(1))
                            cron_parts = line.split('#')[0].strip().split()
                            if len(cron_parts) >= 5:
                                recorders.append({
                                    'hour': hour,
                                    'minute': minute,
                                    'cron_expression': ' '.join(cron_parts[:5]),
                                    'comment': comment
                                })

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
