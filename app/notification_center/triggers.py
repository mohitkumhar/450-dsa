from app.notification_center.models import create_notification

MILESTONE_THRESHOLDS = [10, 25, 50, 100, 150, 200, 300, 450]
STREAK_THRESHOLDS = [7, 14, 30, 60, 100]


def notify_question_milestone(db, user_id, total_done):
    if total_done in MILESTONE_THRESHOLDS:
        create_notification(db, user_id, "milestone",
            f"🎯 {total_done} Questions Done!",
            f"Amazing! You've solved {total_done} DSA questions. Keep going!")


def notify_streak(db, user_id, streak_days):
    if streak_days in STREAK_THRESHOLDS:
        create_notification(db, user_id, "streak",
            f"🔥 {streak_days}-Day Streak!",
            f"You've been solving problems for {streak_days} days straight!")


def notify_sync_failure(db, user_id, platform_name, reason=None):
    message = f"We couldn't sync your {platform_name} profile."
    if reason:
        message += f" Reason: {reason}"
    create_notification(db, user_id, "sync_failure",
        f"⚠️ {platform_name} Sync Failed", message, link="/profile")


def notify_badge_earned(db, user_id, badge_name, badge_description):
    create_notification(db, user_id, "badge",
        f"🏆 Badge Earned: {badge_name}", badge_description, link="/profile")


def notify_goal_completed(db, user_id, goal_name):
    create_notification(db, user_id, "goal",
        "✅ Goal Completed!",
        f"You completed: {goal_name}. Set a new one to keep growing!", link="/profile")
    