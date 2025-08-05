from crontab import CronTab
import sys

if len(sys.argv) < 2 or not sys.argv[1]:
    print("Usage: python3 unschedule.py <comment>")
    exit(1)
cron = CronTab(user=True)

# Find job by comment
cron.remove_all(comment=sys.argv[1])

# Save changes
cron.write()

print(f"Cron job(s) with comment '{sys.argv[1]}' deleted.")
