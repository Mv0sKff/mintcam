import RPi.GPIO as GPIO
import time
import os

def pin_change(channel):
    if GPIO.input(channel) == GPIO.HIGH:
        print("Pin UP")
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        cmd_parts = f'python3 {current_dir}/callback.py video 60'

        os.system(cmd_parts)
    else:
        print("Pin DOWN")

GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Detect both rising and falling edges
GPIO.add_event_detect(21, GPIO.BOTH, callback=pin_change, bouncetime=200)

print("Waiting for pin events on GPIO 21... (Press CTRL+C to exit)")

try:
    while True:
        time.sleep(1)  # keep program alive
except KeyboardInterrupt:
    print("\nExiting program.")
finally:
    GPIO.cleanup()
