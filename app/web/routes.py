from flask import Blueprint, render_template, current_app
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

    public_user_data = {
        "username": user_doc.get("name") or user_doc.get("username", "Unknown User"),
        "avatar_url": user_doc.get("profile_photo") or user_doc.get("avatar_url", ""),
    }

    stats = compute_c_score(user_doc)

    return render_template(
        "public_profile.html",
        user=public_user_data,
        stats=stats
    )


@public_bp.route("/compare/<user_a_id>/<user_b_id>")
def public_compare(user_a_id, user_b_id):
    try:
        user_doc_a = db.user.find_one({"_id": ObjectId(user_a_id)})
        user_doc_b = db.user.find_one({"_id": ObjectId(user_b_id)})
    except InvalidId:
        return "Invalid User ID", 400
    except Exception as exc:
        current_app.logger.exception(f"Failed to load public compare for {user_a_id} vs {user_b_id}: {exc}")
        return "Server Error", 500

    if not user_doc_a or not user_doc_b:
        return "User not found", 404
    # Respect deactivated and explicit privacy flag if present
    for ud in (user_doc_a, user_doc_b):
        if ud.get("is_deactivated"):
            return "User not found", 404
        if ud.get("public_profile") is False:
            return "User not found", 404

    stats_a = compute_c_score(user_doc_a)
    stats_b = compute_c_score(user_doc_b)

    user_a = {
        "username": user_doc_a.get("name") or user_doc_a.get("username", "Unknown User"),
        "avatar_url": user_doc_a.get("profile_photo") or user_doc_a.get("avatar_url", ""),
    }
    user_b = {
        "username": user_doc_b.get("name") or user_doc_b.get("username", "Unknown User"),
        "avatar_url": user_doc_b.get("profile_photo") or user_doc_b.get("avatar_url", ""),
    }

    # Build simple platform totals mapping from compute_c_score result
    platforms_a = {
        "LeetCode": int(stats_a.get("lc_total", 0)),
        "GFG": int(stats_a.get("gfg_total", 0)),
        "Coding Ninjas": int(stats_a.get("cn_total", 0)),
        "HackerRank": int(stats_a.get("hr_total", 0)),
        "AtCoder": int(stats_a.get("atcoder_total", 0) or 0),
        "Codewars": int(stats_a.get("cw_total", 0)),
        "Other": 0,
    }
    platforms_b = {
        "LeetCode": int(stats_b.get("lc_total", 0)),
        "GFG": int(stats_b.get("gfg_total", 0)),
        "Coding Ninjas": int(stats_b.get("cn_total", 0)),
        "HackerRank": int(stats_b.get("hr_total", 0)),
        "AtCoder": int(stats_b.get("atcoder_total", 0) or 0),
        "Codewars": int(stats_b.get("cw_total", 0)),
        "Other": 0,
    }

    return render_template(
        "public_compare.html",
        user_a=user_a,
        user_b=user_b,
        stats_a=stats_a,
        stats_b=stats_b,
        platforms_a=platforms_a,
        platforms_b=platforms_b,
    )
