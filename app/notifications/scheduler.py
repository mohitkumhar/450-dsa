"""
Background scheduler for sending notifications.

This module provides utilities for setting up scheduled tasks to check and send notifications.
It can be integrated with:
- APScheduler (recommended for Flask apps)
- Celery (for distributed task queuing)
- Cron jobs (simple HTTP-based triggers)
- Cloud functions (AWS Lambda, Google Cloud Functions, etc.)

Usage:
------

1. APScheduler (Recommended):
   ```python
   from apscheduler.schedulers.background import BackgroundScheduler
   from app.notifications.scheduler import schedule_notification_checks

   scheduler = BackgroundScheduler()
   schedule_notification_checks(scheduler)
   scheduler.start()
   ```

2. Celery:
   ```python
   from celery import Celery
   from app.notifications.scheduler import check_all_user_notifications

   app = Celery('tasks')

   @app.task
   def periodic_notification_check():
       check_all_user_notifications()

   # Configure beat schedule in celeryconfig.py
   ```

3. Cron Job (Simple HTTP-based):
   ```bash
   # Run every 6 hours
   0 */6 * * * curl -X POST http://localhost:5000/notifications/check-all
   ```

4. Cloud Functions:
   ```python
   # AWS Lambda / Google Cloud Function
   def notification_handler(event, context):
       check_all_user_notifications()
       return {"status": "success"}
   ```
"""

from app.extensions import db
from app.notifications.service import (
    check_review_reminders,
    check_goal_deadlines,
    check_challenge_deadlines,
)


def check_all_user_notifications():
    """Check all users for pending notifications."""
    users = db.user.find({})
    count = 0

    for user in users:
        try:
            user_id = user.get("_id")
            check_review_reminders(user_id)
            check_goal_deadlines(user_id)
            check_challenge_deadlines(user_id)
            count += 1
        except Exception as e:
            print(f"Error checking notifications for user {user.get('_id')}: {e}")

    print(f"Checked notifications for {count} users")
    return count


def schedule_notification_checks(scheduler):
    """
    Schedule notification checks with APScheduler.

    Usage:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        schedule_notification_checks(scheduler)
        scheduler.start()
    """
    scheduler.add_job(
        func=check_all_user_notifications,
        trigger="interval",
        hours=6,  # Run every 6 hours
        id="check_all_user_notifications",
        name="Check all user notifications",
        replace_existing=True,
    )

    print("Notification scheduler configured")


def get_pending_notifications(user_id, limit=10):
    """Get pending notifications for a user."""
    return list(
        db.notifications.find({"user_id": user_id, "sent": False}).limit(limit).sort("created_at", -1)
    )


def mark_notification_sent(notification_id):
    """Mark a notification as sent."""
    db.notifications.update_one({"_id": notification_id}, {"$set": {"sent": True}})
