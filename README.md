# MintCam

A web-based camera interface for Raspberry Pi with live video streaming, picture capture, and automated recording capabilities.

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
flask run --host=0.0.0.0 --port=5000
```

## Configuration

Edit `config.yml` to customize:
```yaml
name: "My Camera"
port: 5000
debug_mode: true  # Set to false for production with real camera
```

## Scanning microscope mode

A second application lives in `scanner/`: a camera mounted on the print head
of a 3D printer (Ender 5 Plus) scans over the bed in a raster pattern while
recording video; the video is then stitched into one high-resolution image.

Enable it in `config.yml`:
```yaml
scanning_cam: true
scanner_port: 5000
camera_height_mm: 70
```

When `scanning_cam` is `true`, the old `app.py` refuses to start (so only one
app occupies the port). Run the scanner app instead:

```
flask --app scanner.webapp run --host=0.0.0.0 --port=5000
```

### Workflow

1. Generate the scan gcode (adjust parameters as needed):
   ```
   python -m scanner.gcode_generator -o scan.gcode
   # see all options: python -m scanner.gcode_generator --help
   ```
   The camera height above the bed defaults to `CAMERA_HEIGHT_MM = 70` in
   `scanner/gcode_generator.py` (or `--camera-height`).
2. Upload/print `scan.gcode` with your normal printer tooling (pure motion,
   no heating/extrusion).
3. In the web UI press **Start Recording** when the scan starts and
   **Stop Recording** when it finishes.
4. Press **Stitch** — the video is stitched into one image shown on the page.

### Stitching CLI (independent of the web UI)

```
python -m scanner.stitch input.mp4 -o stitched.jpg --grid-rows 9 --grid-cols 10 -v
```

Grid compositing (known raster order) is the default; it falls back to
`cv2.Stitcher` automatically. See `python -m scanner.stitch --help`.

### Future work

- Lens distortion calibration: stubbed in `scanner/calibration.py`,
  procedure in [scanner/CALIBRATION.md](scanner/CALIBRATION.md)
- Object detection on stitched images: stubbed in `scanner/detection.py`,
  plan in [scanner/DETECTION.md](scanner/DETECTION.md)

## Autostart
```
sudo cp autostart/mintcam.service /etc/systemd/system
sudo cp autostart/gpio_trigger.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl start mintcam
sudo systemctl enable mintcam
sudo systemctl start gpio_trigger
sudo systemctl enable gpio_trigger
```

## Create wifi hotspot

```
sudo nmcli device wifi hotspot ssid "mintcam" password <password>
```

### Forward traffic from port 5000 to port 80

```
sudo apt install iptables iptables-persistent
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 5000
sudo netfilter-persistent save
```

then open in browser: ![http://10.42.0.1](http://10.42.0.1) (default raspberry pi ip address)
