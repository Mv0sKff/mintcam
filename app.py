from flask import Flask, Response, render_template, request, jsonify
import cv2
import numpy as np
import threading
import yaml

# Set DEBUG_MODE to True for testing without Picamera2
DEBUG_MODE = True

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
            # Show current settings in debug mode
            settings_text = f"{width}x{height} {camera_settings['fps']}fps"
            if camera_settings['hdr']:
                settings_text += " HDR"
            cv2.putText(frame, 'DEBUG MODE', (width//10, height//2),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.putText(frame, settings_text, (width//10, height//2 + 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            bgr = frame  # Already in BGR format
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

@app.route('/video_feed')
def video_feed():
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

if __name__ == '__main__':
    # Run on all interfaces at port 5000
    #app.run(host='0.0.0.0', port=5000, debug=True)
    app.run(host='localhost', port=int(config.get("port", 5000)), debug=DEBUG_MODE)
