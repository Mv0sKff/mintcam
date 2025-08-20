from crontab import CronTab
import os
import sys

if not(len(sys.argv) >= 3 and sys.argv[1].isdigit() and sys.argv[2].isdigit()):
    print("Usage: python3 schedule.py <hour> <minute> [record_type] [duration]")
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
record_type = sys.argv[3] if len(sys.argv) > 3 else 'picture'
duration = sys.argv[4] if len(sys.argv) > 4 else None

cron_expression = convert_to_cron(int(hour), int(minute))
print("Cron expression:", cron_expression)

cron = CronTab(user=True)

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)

# Build comment with record type and duration
comment_parts = [f'recorder h={hour} m={minute} type={record_type}']
if duration and record_type == 'video':
    comment_parts.append(f'duration={duration}')
comment = ' '.join(comment_parts)

# Build command with parameters
cmd_parts = [f'python3 {current_dir}/callback.py', record_type]
if duration and record_type == 'video':
    cmd_parts.append(duration)
command = ' '.join(cmd_parts)

job = cron.new(command=command, comment=comment)

job.setall(cron_expression)

cron.write()
