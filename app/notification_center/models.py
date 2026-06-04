from datetime import datetime, timezone
from bson import ObjectId


def create_notification(db, user_id, notif_type, title, message, link=None):
    notification = {
        "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "link": link,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = db.notification.insert_one(notification)
    return str(result.inserted_id)


def get_user_notifications(db, user_id, limit=20, unread_only=False):
    query = {"user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id}
    if unread_only:
        query["is_read"] = False
    notifications = list(db.notification.find(query).sort("created_at", -1).limit(limit))
    for n in notifications:
        n["_id"] = str(n["_id"])
        n["user_id"] = str(n["user_id"])
        n["created_at"] = n["created_at"].isoformat()
    return notifications


def get_unread_count(db, user_id):
    return db.notification.count_documents({
        "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
        "is_read": False,
    })


def mark_notification_read(db, notif_id, user_id):
    result = db.notification.update_one(
        {"_id": ObjectId(notif_id), "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id},
        {"$set": {"is_read": True}},
    )
    return result.modified_count > 0


def mark_all_read(db, user_id):
    result = db.notification.update_many(
        {"user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id, "is_read": False},
        {"$set": {"is_read": True}},
    )
    return result.modified_count


def delete_notification(db, notif_id, user_id):
    result = db.notification.delete_one(
        {"_id": ObjectId(notif_id), "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id}
    )
    return result.deleted_count > 0