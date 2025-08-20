# MintCam

A web-based camera interface for Raspberry Pi with live video streaming, picture capture, and automated recording capabilities.

## Features

- **Live Video Stream**: Real-time video feed from camera
- **Manual Capture**: Take pictures and record videos on demand
- **Scheduled Recording**: Set up automated picture/video capture at specific intervals
- **Picture Gallery**: View recently captured images
- **Video Gallery**: View recently recorded videos
- **Resolution Control**: Adjust camera resolution and framerate
- **Debug Mode**: Test functionality without physical camera hardware

## Install (on raspberry pi)

```
sudo apt install python3-picamera2 cron ffmpeg
```

```
git clone https://github.com/Mv0sKff/mintcam.git
cd mintcam
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt

# after update of apt package or something idk
# pip install --upgrade --force-reinstall picamera2
# pip install --upgrade --force-reinstall simplejpeg
```

## Run
```
flask run
```

## Usage

### Manual Recording
- **Take Picture**: Click "Take Picture" button for instant photo capture (Ctrl/Cmd + P)
- **Record Video**: Click "Record Video" button and specify duration (1-30 seconds) (Ctrl/Cmd + V)

### Scheduled Recording
1. Set hour interval (0-23) and minute (0-59)
2. Choose recording type: Picture or Video
3. For videos, set duration (1-30 seconds)
4. Click "Add Recorder" to schedule

### File Management
- **Individual Download**: Each picture and video has its own download button
- **Individual Delete**: Each picture and video has its own delete button with confirmation
- **Bulk Download**: "Download All Pictures" and "Download All Videos" buttons create ZIP archives (Ctrl/Cmd + D / Ctrl/Cmd + Shift + D)
- **Bulk Delete**: "Delete All Pictures" and "Delete All Videos" buttons with confirmation
- **View Files**: Click on thumbnails to view full-size images or play videos

### Keyboard Shortcuts
- **Ctrl/Cmd + P**: Take Picture
- **Ctrl/Cmd + V**: Record Video
- **Ctrl/Cmd + D**: Download All Pictures
- **Ctrl/Cmd + Shift + D**: Download All Videos

### Examples
- Every 30 minutes: Hour=0, Minute=30
- Every 2 hours at 15 minutes past: Hour=2, Minute=15
- Every hour on the hour: Hour=1, Minute=0

### Download Features
- **Individual Downloads**: Direct download of any picture or video file
- **Bulk Downloads**: ZIP archives with timestamp naming (e.g., `mintcam_pictures_20240101_120000.zip`)
- **Smart Error Handling**: Checks for available files before attempting downloads
- **Progress Feedback**: Status messages show download progress and file counts

## Configuration

Edit `config.yml` to customize:
```yaml
name: "My Camera"
port: 5000
debug_mode: true  # Set to false for production with real camera
```

## Autostart
```
sudo cp autostart/mintcam.service /etc/systemd/system
sudo systemctl start mintcam
sudo systemctl enable mintcam
```
