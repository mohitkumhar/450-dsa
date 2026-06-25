from flask import Blueprint, render_template, current_app
from flask_login import current_user
from bson import ObjectId
from bson.errors import InvalidId
from app.extensions import db
from app.utils import compute_c_score

public_bp = Blueprint("public", __name__)


@public_bp.route("/u/<user_id>")
def public_profile(user_id):
    try:
        user_doc = db.user.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        return "Invalid User ID", 400
    except Exception as exc:
        current_app.logger.exception(f"Failed to load public profile for user {user_id}: {exc}")
        return "Server Error", 500

    if not user_doc:
        return "User not found", 404

    if user_doc.get("is_deactivated"):
        return "User not found", 404

    visibility = user_doc.get("profile_visibility", "public")
    viewer_is_owner = (
        current_user.is_authenticated
        and str(current_user.id) == str(user_doc.get("_id"))
    )

    stats = compute_c_score(user_doc)

    if visibility == "private" and not viewer_is_owner:
        return render_template(
            "public_profile.html",
            user={
                "username": "Private Profile",
                "avatar_url": "",
            },
            stats={},
            is_private=True,
            is_stats_only=False,
        )

    if visibility == "stats_only" and not viewer_is_owner:
        return render_template(
            "public_profile.html",
            user={
                "username": "Stats Only Profile",
                "avatar_url": "",
            },
            stats=stats,
            is_private=False,
            is_stats_only=True,
        )

    public_user_data = {
        "username": user_doc.get("name") or user_doc.get("username", "Unknown User"),
        "avatar_url": user_doc.get("profile_photo") or user_doc.get("avatar_url", ""),
    }

    return render_template(
        "public_profile.html",
        user=public_user_data,
        stats=stats,
        is_private=False,
        is_stats_only=False,
    )