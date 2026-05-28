from app.badges.definitions import BADGES
from app.badges.models import award_badge


def get_user_stats(user):
    progress = user.get("progress", {}) if isinstance(user, dict) else getattr(user, "progress", {})
    solved = sum(1 for p in progress.values() if p.get("done"))
    streak = getattr(user, "current_streak", 0) or 0
    platforms = len(getattr(user, "linked_platforms", []) or [])
    return {"solved": solved, "streak": streak, "platforms": platforms}


def evaluate_and_award_badges(user):
    stats     = get_user_stats(user)
    solved    = stats["solved"]
    streak    = stats["streak"]
    platforms = stats["platforms"]

    newly_awarded = []
    user_id = getattr(user, "id", None) or user.get("_id")

    for badge in BADGES:
        if eval(badge["condition"]):
            awarded = award_badge(user_id, badge["key"], badge["name"])
            if awarded:
                newly_awarded.append(badge["name"])

    return newly_awarded