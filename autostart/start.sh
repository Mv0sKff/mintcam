#!/bin/bash

cd /home/pi/MintCam
source venv/bin/activate

export FLASK_APP=app.py

flask run --host=0.0.0.0 --port=5000