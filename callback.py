import requests, os
from datetime import datetime

log_folder_path = "logs/"
log_file_name = "log.txt"
log_file_path = log_folder_path + log_file_name
url = 'http://localhost:5000/take_picture'
data = {}

response = requests.post(url, data)

if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"Request failed with status code {response.status_code}")

# logging
os.makedirs(log_folder_path, exist_ok=True)
now = datetime.now()
current_time = now.strftime("%H:%M:%S")

with open(log_file_path, 'w') as file:
    file.write(f"took pic at {current_time} {data}\n")
