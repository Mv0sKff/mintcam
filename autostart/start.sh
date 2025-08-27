#!/bin/bash

cd /home/pi/mintcam
source .venv/bin/activate

./autostart/update.sh

export FLASK_APP=app.py

python -m flask run --host=0.0.0.0 --port=5000
