from crontab import CronTab
import sys

if not sys.argv[1]:
    exit(1)
cron = CronTab(user=True)

# Find job by comment
cron.remove_all(comment=sys.argv[1])

# Save changes
cron.write()

print("Cron job(s) with comment 'my_daily_task' deleted.")
