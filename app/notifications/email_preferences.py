from datetime import datetime
from bson import ObjectId
from app.extensions import db


def init_email_preferences(user_id):
    """Create default email preferences for a new user."""
    existing = db.email_preferences.find_one({"user_id": ObjectId(user_id)})
    if existing:
        return existing

    prefs = {
        "user_id": ObjectId(user_id),
        "product_updates": True,
        "study_reminders": True,
        "sync_failures": True,
        "achievement_emails": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = db.email_preferences.insert_one(prefs)
    prefs["_id"] = result.inserted_id
    return prefs


def get_email_preferences(user_id):
    """Get email preferences for a user."""
    return db.email_preferences.find_one({"user_id": ObjectId(user_id)})


def update_email_preference(user_id, pref_type, enabled):
    """Update a specific email preference."""
    valid_types = ["product_updates", "study_reminders", "sync_failures", "achievement_emails"]
    
    if pref_type not in valid_types:
        return False

    result = db.email_preferences.update_one(
        {"user_id": ObjectId(user_id)},
        {
            "$set": {
                pref_type: enabled,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    return result.modified_count > 0 or result.upserted_id is not None


def should_send_email(user_id, email_type):
    """Check if we should send an email to this user."""
    if email_type not in ["product_updates", "study_reminders", "sync_failures", "achievement_emails"]:
        return False

    prefs = get_email_preferences(user_id)
    if not prefs:
        return False

    return prefs.get(email_type, False)