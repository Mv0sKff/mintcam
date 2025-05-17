from flask import Flask, Response, render_template
from picamera2 import Picamera2
import cv2
import threading

# Initialize Flask app
app = Flask(__name__)

# Initialize Picamera2
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={'format': 'XRGB8888', 'size': (640, 480)}
)
picam2.configure(config)
picam2.start()

# Generator for MJPEG stream
def gen_frames():
    while True:
        # Capture frame as numpy array
        frame = picam2.capture_array('main')
        # Convert from RGBX to BGR for JPEG encoding
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        # Encode as JPEG
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
    return render_template('index.html')

if __name__ == '__main__':
    # Run on all interfaces at port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)