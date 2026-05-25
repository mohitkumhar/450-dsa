from flask import Blueprint, current_app, render_template
from bson import ObjectId
from bson.errors import InvalidId
from app.extensions import db
from app.github_showcase import fetch_github_repo_showcase
from app.utils import compute_c_score

public_bp = Blueprint("public", __name__)

@public_bp.route("/u/<user_id>")
def public_profile(user_id):
    try:
        user_doc = db.user.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        return "Invalid User ID", 400
    except Exception:
        return "Server Error", 500

    if not user_doc:
        return "User not found", 404

    public_user_data = {
        "username": user_doc.get("name") or user_doc.get("username", "Unknown User"),
        "avatar_url": user_doc.get("profile_photo") or user_doc.get("avatar_url", ""),
        "github_username": user_doc.get("github_username", ""),
    }

    stats = compute_c_score(user_doc)
    github_repos = []
    try:
        github_repos = fetch_github_repo_showcase(
            user_doc.get("github_username", ""),
            user_doc.get("github_repo_list", ""),
        )
    except Exception:
        current_app.logger.exception("Failed to load public GitHub repository showcase")

    return render_template(
        "public_profile.html",
        user=public_user_data,
        stats=stats,
        github_repos=github_repos,
    )
