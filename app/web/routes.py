import re

from flask import Blueprint, render_template, current_app
from bson import ObjectId
from bson.errors import InvalidId
from app.extensions import db
from app.leaderboard.service import build_leaderboard_data
from app.utils import compute_c_score

public_bp = Blueprint("public", __name__)


def _college_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

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


@public_bp.route("/college/<slug>")
def college_detail(slug):
    entries = build_leaderboard_data()

    slug_to_college = {}
    for entry in entries:
        college = (entry.get("college") or "").strip()
        if college:
            slug_to_college[_college_slug(college)] = college

    college_name = slug_to_college.get(slug)
    if not college_name:
        return "College not found", 404

    members = [e for e in entries if (e.get("college") or "").strip().lower() == college_name.lower()]
    member_count = len(members)
    total_solved = sum(e.get("total_solved", 0) for e in members)
    c_score_sum = sum(e.get("c_score", 0) for e in members)
    dsa_done = sum(e.get("dsa_done", 0) for e in members)
    lc_total = sum(e.get("lc_total", 0) for e in members)
    gfg_total = sum(e.get("gfg_total", 0) for e in members)
    cn_total = sum(e.get("cn_total", 0) for e in members)
    hr_total = sum(e.get("hr_total", 0) for e in members)

    rated_members = [e for e in members if e.get("lc_rating", 0)]
    avg_rating = round(sum(e.get("lc_rating", 0) for e in rated_members) / len(rated_members)) if rated_members else 0

    members_sorted = sorted(members, key=lambda e: e.get("c_score", 0), reverse=True)

    return render_template(
        "college_detail.html",
        college=college_name,
        member_count=member_count,
        total_solved=total_solved,
        avg_c_score=round(c_score_sum / member_count) if member_count else 0,
        avg_rating=avg_rating,
        dsa_done=dsa_done,
        lc_total=lc_total,
        gfg_total=gfg_total,
        cn_total=cn_total,
        hr_total=hr_total,
        members=members_sorted,
    )
