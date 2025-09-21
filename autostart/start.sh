#!/bin/bash

cd /home/pi/mintcam
source .venv/bin/activate

./autostart/update.sh

python app.py
