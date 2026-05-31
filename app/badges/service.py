from app.badges.definitions import BADGES
from app.badges.models import award_badge
from app.notifications.service import notify_badge_earned


def get_user_stats(user):
    """Extract solved, streak, platforms stats from user."""
    progress = (
        user.get("progress", {})
        if isinstance(user, dict)
        else getattr(user, "progress", {})
    )
    solved = sum(1 for p in progress.values() if p.get("done"))
    streak = getattr(user, "current_streak", 0) or 0
    platforms = len(getattr(user, "linked_platforms", []) or [])
    return {"solved": solved, "streak": streak, "platforms": platforms}


def evaluate_and_award_badges(user):
    """Check and award any newly earned badges for the user."""
    stats = get_user_stats(user)
    newly_awarded = []
    user_id = getattr(user, "id", None) or user.get("_id")
    for badge in BADGES:
        solved = stats["solved"]  # noqa: F841
        streak = stats["streak"]  # noqa: F841
        platforms = stats["platforms"]  # noqa: F841
        if eval(badge["condition"]):
            if award_badge(user_id, badge["key"], badge["name"]):
                newly_awarded.append(badge["name"])
                notify_badge_earned(user_id, badge["name"])
    return newly_awarded
