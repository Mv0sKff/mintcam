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
flask run --host=0.0.0.0
```

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
