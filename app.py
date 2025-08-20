from flask import Flask, Response, render_template, request, jsonify, send_file
import cv2
import numpy as np
import yaml
import os
import subprocess
from datetime import datetime
import threading
import time
import zipfile
import io
import shutil
from PIL import Image

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
            # Use PIL for JPEG encoding to preserve RGB color format
            img = Image.fromarray(frame, 'RGB')
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            frame_bytes = img_buffer.getvalue()
        else:
            # Capture frame from camera
            frame = picam2.capture_array('main')
            # Use PIL for JPEG encoding to preserve BGR color format
            img = Image.fromarray(frame, 'BGR')
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
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # Add some visual content to the debug image
            cv2.putText(frame, f'Debug Image {timestamp}', (50, height//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            # Use PIL to save image directly from RGB format
            img = Image.fromarray(frame, 'RGB')
            img.save(filepath, format='JPEG', quality=95)
            success = True
        else:
            # Capture a high-quality still image from camera
            frame = picam2.capture_array('main')
            # Use PIL to save image directly from BGR format
            img = Image.fromarray(frame, 'BGR')
            img.save(filepath, format='JPEG', quality=95)
            success = True

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

        # Check if download parameter is present
        download = request.args.get('download', 'false').lower() == 'true'

        if download:
            return send_file(filepath, mimetype='image/jpeg', as_attachment=True, download_name=filename)
        else:
            return send_file(filepath, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error serving picture: {str(e)}'
        }), 500

@app.route('/delete_picture/<filename>', methods=['DELETE'])
def delete_picture(filename):
    try:
        # Security: Prevent path traversal attacks
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid filename'
            }), 400

        pictures_dir = 'pictures'
        filepath = os.path.join(pictures_dir, filename)

        # Security: Ensure file is actually in the pictures directory
        if not os.path.commonpath([os.path.abspath(pictures_dir), os.path.abspath(filepath)]) == os.path.abspath(pictures_dir):
            return jsonify({
                'success': False,
                'message': 'Invalid file path'
            }), 400

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Picture not found'
            }), 404

        # Verify it's an image file
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return jsonify({
                'success': False,
                'message': 'Invalid file type'
            }), 400

        # Delete the file
        os.remove(filepath)

        return jsonify({
            'success': True,
            'message': f'Picture {filename} deleted successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting picture: {str(e)}'
        }), 500

@app.route('/delete_all_pictures', methods=['DELETE'])
def delete_all_pictures():
    try:
        pictures_dir = 'pictures'
        if not os.path.exists(pictures_dir):
            return jsonify({
                'success': True,
                'message': 'No pictures directory found',
                'deleted_count': 0
            })

        deleted_count = 0
        for filename in os.listdir(pictures_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(pictures_dir, filename)
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")

        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} pictures',
            'deleted_count': deleted_count
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting pictures: {str(e)}'
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

            video_recording['is_recording'] = True
            video_recording['output_path'] = filepath

            try:
                # Try OpenCV method first (more reliable)
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(filepath, fourcc, camera_settings['fps'], (width, height))

                total_frames = duration * camera_settings['fps']
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for frame_num in range(total_frames):
                    # Create a blue frame
                    frame = np.full((height, width, 3), (255, 0, 0), dtype=np.uint8)

                    # Add text overlay
                    cv2.putText(frame, 'DEBUG MODE', (50, 50),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv2.putText(frame, f'Recording: {timestamp}', (50, 100),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(frame, f'Frame: {frame_num}/{total_frames}', (50, 150),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                    out.write(frame)

                out.release()

                video_recording['is_recording'] = False
                video_recording['output_path'] = None

                return jsonify({
                    'success': True,
                    'message': f'Debug video recorded successfully ({duration}s)',
                    'filename': filename,
                    'filepath': filepath,
                    'duration': duration
                })

            except Exception as opencv_error:
                # Fallback to FFmpeg if OpenCV fails
                if shutil.which('ffmpeg'):
                    try:
                        # Simple solid color video without text
                        ffmpeg_cmd = [
                            'ffmpeg', '-f', 'lavfi', '-i',
                            f'color=color=blue:size={width}x{height}:duration={duration}:rate={camera_settings["fps"]}',
                            '-pix_fmt', 'yuv420p', '-y', filepath
                        ]

                        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

                        if result.returncode == 0:
                            video_recording['is_recording'] = False
                            video_recording['output_path'] = None

                            return jsonify({
                                'success': True,
                                'message': f'Debug video created with FFmpeg ({duration}s)',
                                'filename': filename,
                                'filepath': filepath,
                                'duration': duration
                            })
                        else:
                            raise Exception(f'FFmpeg failed: {result.stderr}')

                    except Exception as ffmpeg_error:
                        video_recording['is_recording'] = False
                        video_recording['output_path'] = None
                        return jsonify({
                            'success': False,
                            'message': f'Debug video creation failed. OpenCV error: {opencv_error}. FFmpeg error: {ffmpeg_error}'
                        }), 500
                else:
                    video_recording['is_recording'] = False
                    video_recording['output_path'] = None
                    # Final fallback - create a simple text file as placeholder
                    try:
                        fallback_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        with open(filepath.replace('.mp4', '.txt'), 'w') as f:
                            f.write(f"Debug video recording simulated\n")
                            f.write(f"Duration: {duration} seconds\n")
                            f.write(f"Resolution: {width}x{height}\n")
                            f.write(f"FPS: {camera_settings['fps']}\n")
                            f.write(f"Timestamp: {fallback_timestamp}\n")
                            f.write(f"Note: OpenCV and FFmpeg both unavailable\n")

                        return jsonify({
                            'success': True,
                            'message': f'Debug recording simulated (saved as text file)',
                            'filename': filename.replace('.mp4', '.txt'),
                            'filepath': filepath.replace('.mp4', '.txt'),
                            'duration': duration
                        })
                    except Exception as file_error:
                        return jsonify({
                            'success': False,
                            'message': f'All debug methods failed. OpenCV: {opencv_error}. File write: {file_error}'
                        }), 500
        else:
            # Record video using picamera2
            from picamera2.encoders import H264Encoder
            from picamera2.outputs import FileOutput

            video_recording['is_recording'] = True
            video_recording['output_path'] = filepath

            # Create temporary H264 file
            h264_filepath = filepath.replace('.mp4', '.h264')

            try:
                # Stop the current video stream temporarily
                picam2.stop()

                # Configure for video recording
                video_config = picam2.create_video_configuration(
                    main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
                )
                picam2.configure(video_config)

                # Create encoder and output for H264 format
                encoder = H264Encoder()
                output = FileOutput(h264_filepath)

                # Start recording
                picam2.start_recording(encoder, output)

                # Record for the specified duration
                time.sleep(duration)

                # Stop recording
                picam2.stop_recording()

                # Convert H264 to MP4 using ffmpeg
                convert_success = False

                # Check if ffmpeg is available
                if shutil.which('ffmpeg'):
                    try:
                        ffmpeg_cmd = [
                            'ffmpeg', '-i', h264_filepath, '-c', 'copy',
                            '-f', 'mp4', '-y', filepath
                        ]
                        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            convert_success = True
                            # Remove the temporary H264 file
                            os.remove(h264_filepath)
                        else:
                            print(f"FFmpeg conversion failed: {result.stderr}")
                    except Exception as ffmpeg_error:
                        print(f"FFmpeg failed: {ffmpeg_error}")
                else:
                    print("FFmpeg not found in PATH")

                # If conversion failed, keep the H264 file as MP4 (will play in most browsers)
                if not convert_success and os.path.exists(h264_filepath):
                    os.rename(h264_filepath, filepath)
                    print(f"Video saved as H264 format: {filepath}")

                # Final check - ensure we have a video file
                if not os.path.exists(filepath):
                    raise Exception("Video file was not created successfully")

                # Restart the video stream for live feed
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
                # Clean up temporary file if it exists
                if os.path.exists(h264_filepath):
                    try:
                        os.remove(h264_filepath)
                    except:
                        pass

                # Ensure we restart the stream even if recording fails
                try:
                    stream_config = picam2.create_video_configuration(
                        main={'format': 'RGB888', 'size': (camera_settings['width'], camera_settings['height'])}
                    )
                    picam2.configure(stream_config)
                    picam2.start()
                except Exception as stream_error:
                    print(f"Failed to restart video stream: {stream_error}")

                video_recording['is_recording'] = False
                video_recording['output_path'] = None

                # Provide more detailed error message
                error_msg = f"Video recording failed: {str(e)}"
                if "H264Encoder" in str(e):
                    error_msg += ". Try installing: sudo apt install python3-picamera2"
                elif "FileOutput" in str(e):
                    error_msg += ". Check file permissions and disk space."
                elif "ffmpeg" in str(e).lower():
                    error_msg += ". Install ffmpeg: sudo apt install ffmpeg"
                elif "Camera already started" in str(e):
                    error_msg += ". Camera is busy. Try again in a moment."

                return jsonify({
                    'success': False,
                    'message': error_msg
                }), 500

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
            if filename.lower().endswith(('.mp4', '.avi', '.mov', '.h264', '.txt')):
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

        # Check if download parameter is present
        download = request.args.get('download', 'false').lower() == 'true'

        # Determine mimetype based on file extension
        if filename.lower().endswith('.h264'):
            mimetype = 'video/h264'
        elif filename.lower().endswith('.avi'):
            mimetype = 'video/x-msvideo'
        elif filename.lower().endswith('.mov'):
            mimetype = 'video/quicktime'
        elif filename.lower().endswith('.txt'):
            mimetype = 'text/plain'
        else:
            mimetype = 'video/mp4'

        if download:
            return send_file(filepath, mimetype=mimetype, as_attachment=True, download_name=filename)
        else:
            return send_file(filepath, mimetype=mimetype)

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error serving video: {str(e)}'
        }), 500

@app.route('/delete_video/<filename>', methods=['DELETE'])
def delete_video(filename):
    try:
        # Security: Prevent path traversal attacks
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid filename'
            }), 400

        videos_dir = 'videos'
        filepath = os.path.join(videos_dir, filename)

        # Security: Ensure file is actually in the videos directory
        if not os.path.commonpath([os.path.abspath(videos_dir), os.path.abspath(filepath)]) == os.path.abspath(videos_dir):
            return jsonify({
                'success': False,
                'message': 'Invalid file path'
            }), 400

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Video not found'
            }), 404

        # Verify it's a video file or debug file
        if not filename.lower().endswith(('.mp4', '.avi', '.mov', '.h264', '.txt')):
            return jsonify({
                'success': False,
                'message': 'Invalid file type'
            }), 400

        # Delete the file
        os.remove(filepath)

        return jsonify({
            'success': True,
            'message': f'Video {filename} deleted successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting video: {str(e)}'
        }), 500

@app.route('/delete_all_videos', methods=['DELETE'])
def delete_all_videos():
    try:
        videos_dir = 'videos'
        if not os.path.exists(videos_dir):
            return jsonify({
                'success': True,
                'message': 'No videos directory found',
                'deleted_count': 0
            })

        deleted_count = 0
        for filename in os.listdir(videos_dir):
            if filename.lower().endswith(('.mp4', '.avi', '.mov', '.h264', '.txt')):
                filepath = os.path.join(videos_dir, filename)
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")

        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} videos',
            'deleted_count': deleted_count
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting videos: {str(e)}'
        }), 500

@app.route('/download_all_pictures')
def download_all_pictures():
    try:
        pictures_dir = 'pictures'
        if not os.path.exists(pictures_dir):
            return jsonify({
                'success': False,
                'message': 'No pictures directory found'
            }), 404

        # Create a zip file in memory
        memory_file = io.BytesIO()

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            file_count = 0
            for filename in os.listdir(pictures_dir):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    filepath = os.path.join(pictures_dir, filename)
                    if os.path.exists(filepath):
                        zf.write(filepath, filename)
                        file_count += 1

            if file_count == 0:
                return jsonify({
                    'success': False,
                    'message': 'No pictures found to download'
                }), 404

        memory_file.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'mintcam_pictures_{timestamp}.zip'

        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating pictures archive: {str(e)}'
        }), 500

@app.route('/download_all_videos')
def download_all_videos():
    try:
        videos_dir = 'videos'
        if not os.path.exists(videos_dir):
            return jsonify({
                'success': False,
                'message': 'No videos directory found'
            }), 404

        # Create a zip file in memory
        memory_file = io.BytesIO()

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            file_count = 0
            for filename in os.listdir(videos_dir):
                if filename.lower().endswith(('.mp4', '.avi', '.mov')):
                    filepath = os.path.join(videos_dir, filename)
                    if os.path.exists(filepath):
                        zf.write(filepath, filename)
                        file_count += 1

            if file_count == 0:
                return jsonify({
                    'success': False,
                    'message': 'No videos found to download'
                }), 404

        memory_file.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'mintcam_videos_{timestamp}.zip'

        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating videos archive: {str(e)}'
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
