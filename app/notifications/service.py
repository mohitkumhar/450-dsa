from datetime import datetime, timedelta
from bson import ObjectId
from app.extensions import db
from app.notifications.models import should_send_notification


def send_push_notification(user_id, title, body, data=None):
    """
    Store notification in database for service worker to send.
    In production, integrate with a push notification service.
    """
    notification_doc = {
        "user_id": ObjectId(user_id),
        "title": title,
        "body": body,
        "data": data or {},
        "created_at": datetime.utcnow(),
        "sent": False,
    }
    return db.notifications.insert_one(notification_doc)


def notify_milestone_reached(user_id, question_count):
    """Send notification when user reaches question-solving milestones."""
    milestones = [50, 100, 150, 200, 250, 300, 350, 450]
    if question_count not in milestones:
        return False

    if not should_send_notification(user_id, "due_goals"):
        return False

    milestone_messages = {
        50: "🎉 You've solved 50 questions! Keep the momentum going!",
        100: "💯 100 questions completed! You're crushing it!",
        150: "🚀 150 problems down! Halfway to the ultimate goal!",
        200: "🔥 200 DSA problems solved! You're a coding machine!",
        250: "⭐ Quarter way through 450! Amazing progress!",
        300: "👑 300 problems mastered! You're a DSA expert!",
        350: "🏆 350 problems conquered! Almost there!",
        450: "🎊 CONGRATULATIONS! You've completed all 450 DSA problems!",
    }

    message = milestone_messages.get(question_count, f"Milestone: {question_count} questions solved!")
    send_push_notification(
        user_id,
        title="Milestone Reached! 🎯",
        body=message,
        data={"type": "milestone", "count": question_count},
    )
    return True


def notify_streak_milestone(user_id, streak_days):
    """Send notification when user reaches streak milestones."""
    streak_milestones = [7, 14, 30, 60, 100]
    if streak_days not in streak_milestones:
        return False

    if not should_send_notification(user_id, "reminders"):
        return False

    streak_messages = {
        7: "🔥 7-day streak! You're on fire!",
        14: "💪 2-week streak! Keep it up!",
        30: "🎯 30-day streak! Consistency is key!",
        60: "⚡ 60-day streak! You're unstoppable!",
        100: "👑 100-day streak! You're a DSA legend!",
    }

    message = streak_messages.get(streak_days, f"You have a {streak_days}-day streak!")
    send_push_notification(
        user_id,
        title="Streak Milestone! 🔥",
        body=message,
        data={"type": "streak", "days": streak_days},
    )
    return True


def notify_question_solved(user_id, problem_name):
    """Send immediate notification when question is solved."""
    if not should_send_notification(user_id, "due_goals"):
        return False

    send_push_notification(
        user_id,
        title="Problem Solved! ✅",
        body=f"Great job solving '{problem_name}'!",
        data={"type": "question_solved", "problem": problem_name},
    )
    return True


def check_review_reminders(user_id):
    """
    Check if user should get a review reminder.
    Send reminder if user hasn't solved a problem in 3 days.
    """
    if not should_send_notification(user_id, "reminders"):
        return False

    user = db.user.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("progress"):
        return False

    # Find most recent problem solved
    most_recent = None
    for problem_id, progress_item in user.get("progress", {}).items():
        if progress_item.get("timestamp"):
            ts = progress_item["timestamp"]
            if most_recent is None or ts > most_recent:
                most_recent = ts

    if not most_recent:
        return False

    days_since = (datetime.utcnow() - most_recent).days
    if days_since >= 3:
        send_push_notification(
            user_id,
            title="Time to Review! 📚",
            body=f"You haven't solved a problem in {days_since} days. Let's keep your streak!",
            data={"type": "review_reminder", "days_since": days_since},
        )
        return True

    return False


def check_goal_deadlines(user_id):
    """
    Check for due goals and send notifications.
    This is a hook for future goal/challenge features.
    """
    if not should_send_notification(user_id, "due_goals"):
        return False

    goals = list(db.goals.find({"user_id": ObjectId(user_id), "due_date": {"$lte": datetime.utcnow()}}))

    for goal in goals:
        if goal.get("notified"):
            continue

        send_push_notification(
            user_id,
            title="Goal Reminder! 🎯",
            body=f"Your goal '{goal.get('title')}' is due now!",
            data={"type": "goal_due", "goal_id": str(goal["_id"])},
        )

        # Mark as notified
        db.goals.update_one({"_id": goal["_id"]}, {"$set": {"notified": True}})

    return len(goals) > 0


def check_challenge_deadlines(user_id):
    """
    Check for upcoming challenge deadlines and send notifications.
    This is a hook for future challenge features.
    """
    if not should_send_notification(user_id, "challenges"):
        return False

    # Check for challenges due in next 24 hours
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)

    challenges = list(
        db.challenges.find(
            {
                "user_id": ObjectId(user_id),
                "due_date": {"$gt": now, "$lte": tomorrow},
                "notified": False,
            }
        )
    )

    for challenge in challenges:
        hours_left = int(((challenge.get("due_date") - now).total_seconds() / 3600))
        send_push_notification(
            user_id,
            title="Challenge Deadline Alert! ⏰",
            body=f"Challenge '{challenge.get('title')}' due in {hours_left} hours",
            data={"type": "challenge_deadline", "challenge_id": str(challenge["_id"])},
        )

        # Mark as notified
        db.challenges.update_one({"_id": challenge["_id"]}, {"$set": {"notified": True}})

    return len(challenges) > 0
