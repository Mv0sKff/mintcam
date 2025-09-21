#!/bin/bash

cd /home/pi/mintcam
source .venv/bin/activate

./autostart/update.sh

./autostart/wifi.sh

sudo python app.py
