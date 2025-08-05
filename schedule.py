from crontab import CronTab
import os
import sys

if not(len(sys.argv) >= 3 and sys.argv[1].isalnum() and sys.argv[1].isalnum()):
    print("crie")
    exit(1)

# TODO fix hour = 0
def convert_to_cron(hour: int = None, minute: int = None) -> str:
    """
    Converts hour and/or minute interval to a cron expression.

    Args:
        hour (int, optional): Hour interval (e.g. every 2 hours)
        minute (int, optional): Minute or minute interval (e.g. every 5 minutes or minute of the hour)

    Returns:
        str: A cron expression
    """

    # Every X minutes (e.g., every 5 minutes)
    if (hour is None or hour == 0) and minute is not None:
        if 1 <= minute <= 59:
            return f"*/{minute} * * * *"
        elif minute == 0:
            return f"0 * * * *"
        else:
            raise ValueError("Minute interval must be between 1 and 59.")

    # Every X hours at Y minute
    elif hour is not None and minute is not None:
        if not (0 <= minute <= 59):
            raise ValueError("Minute must be between 0 and 59.")
        if not (1 <= hour <= 23):
            raise ValueError("Hour interval must be between 1 and 23.")
        return f"{minute} */{hour} * * *"

    else:
        raise ValueError("Invalid input: must specify minute or both hour and minute.")

hour = sys.argv[1]
minute = sys.argv[2]

cron_expression = convert_to_cron(int(hour), int(minute))
print("Cron expression:", cron_expression)

cron = CronTab(user=True)

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)

job = cron.new(command=f'python3 {current_dir}/callback.py', comment=f'recorder h={hour} m={minute}')

job.setall(cron_expression)

cron.write()
