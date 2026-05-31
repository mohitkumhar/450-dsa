from app.extensions import mongo
from datetime import datetime


def award_badge(user_id, badge_key, badge_name):
    """Award a badge to a user. Returns True if newly awarded."""
    existing = mongo.db.badges.find_one(
        {"user_id": user_id, "badge_key": badge_key}
    )
    if existing:
        return False
    mongo.db.badges.insert_one({
        "user_id": user_id,
        "badge_key": badge_key,
        "badge_name": badge_name,
        "earned_at": datetime.utcnow()
    })
    return True


def get_user_badges(user_id):
    """Get all badges earned by a user."""
    return list(mongo.db.badges.find(
        {"user_id": user_id},
        {"_id": 0, "badge_key": 1, "badge_name": 1, "earned_at": 1}
    ).sort("earned_at", 1))
