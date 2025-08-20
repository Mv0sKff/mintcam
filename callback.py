import requests, os, sys
from datetime import datetime
import json

log_folder_path = "logs/"
log_file_name = "log.txt"
log_file_path = log_folder_path + log_file_name

# Get recording type from command line arguments
record_type = sys.argv[1] if len(sys.argv) > 1 else 'picture'
duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30

# Determine URL and data based on recording type
if record_type == 'video':
    url = 'http://localhost:5000/record_video'
    data = {'duration': duration}
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    action_text = f"recorded {duration}s video"
else:
    url = 'http://localhost:5000/take_picture'
    data = {}
    response = requests.post(url, data)
    action_text = "took picture"

if response.status_code == 200:
    response_data = response.json()
    print(response_data)
else:
    print(f"Request failed with status code {response.status_code}")
    response_data = {"error": f"HTTP {response.status_code}"}

# logging
os.makedirs(log_folder_path, exist_ok=True)
now = datetime.now()
current_time = now.strftime("%H:%M:%S")

with open(log_file_path, 'a') as file:
    file.write(f"{action_text} at {current_time} {response_data}\n")
