# MintCam

## Install

```
sudo apt install python3-picamera
```

```
git clone https://github.com/Mv0sKff/mintcam.git
cd mintcam
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```
flask run
```

## Autostart
```
sudo cp autostart/mintcam.service /etc/systemd/system
sudo systemctl start mintcam
sudo systemctl enable mintcam
```
