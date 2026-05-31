from app.notifications.models import create_notification


def notify_sync_failure(user_id, platform):
    """Notify user of a platform sync failure."""
    create_notification(
        user_id=user_id,
        notif_type="sync_failure",
        message=f"Sync failed for {platform}. Please reconnect."
    )


def notify_sync_success(user_id, platform):
    """Notify user of a successful platform sync."""
    create_notification(
        user_id=user_id,
        notif_type="sync_success",
        message=f"Successfully synced {platform} profile!"
    )


def notify_badge_earned(user_id, badge_name):
    """Notify user of a newly earned badge."""
    create_notification(
        user_id=user_id,
        notif_type="badge",
        message=f"🏅 You earned the '{badge_name}' badge!"
    )


def notify_goal_completed(user_id, goal):
    """Notify user of a completed goal."""
    create_notification(
        user_id=user_id,
        notif_type="goal",
        message=f"🎯 Goal completed: {goal}"
    )


def notify_account_event(user_id, event):
    """Notify user of an important account event."""
    create_notification(
        user_id=user_id,
        notif_type="account",
        message=event
    )
    