from flask import Blueprint, render_template, current_app
from bson import ObjectId
from bson.errors import InvalidId
from flask_login import current_user
from app.extensions import db
from app.utils import compute_c_score

public_bp = Blueprint("public", __name__)

@public_bp.route("/u/<user_id>")
def public_profile(user_id):
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return "Invalid User ID", 400
    except Exception as exc:
        current_app.logger.exception(f"Failed to load public profile for user {user_id}: {exc}")
        return "Server Error", 500

    try:
        user_doc = db.user.find_one({"_id": oid})
    except Exception as exc:
        current_app.logger.exception(f"Failed to load public profile for user {user_id}: {exc}")
        return "Server Error", 500

    if not user_doc:
        return "User not found", 404
    if user_doc.get("is_deactivated"):
        return "User not found", 404

    # Determine if this is the viewer's own profile.
    viewer_id = current_user.id if current_user.is_authenticated else None
    is_own_profile = viewer_id is not None and viewer_id == oid

    # Enforce privacy: non-owners cannot view private profiles.
    if user_doc.get("is_public") is False and not is_own_profile:
        return "User not found", 404

    public_user_data = {
        "username": user_doc.get("name") or user_doc.get("username", "Unknown User"),
        "avatar_url": user_doc.get("profile_photo") or user_doc.get("avatar_url", ""),
    }

    stats = compute_c_score(user_doc)

    # Determine follow state for the current viewer.
    is_following = False
    if viewer_id is not None and not is_own_profile:
        is_following = bool(db.follows.find_one({"follower_id": viewer_id, "followed_id": oid}))

    return render_template(
        "public_profile.html",
        user=public_user_data,
        stats=stats,
        target_user_id=user_id,
        is_own_profile=is_own_profile,
        is_following=is_following,
    )
