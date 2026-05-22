from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from app.extensions import limiter, cache
from app.utils import build_college_leaderboard_data, build_leaderboard_data


leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard")
@limiter.limit("20 per minute")
@cache.cached(timeout=300)
def leaderboard():
    entries = build_leaderboard_data()

    by_cscore = sorted(entries, key=lambda item: item["c_score"], reverse=True)
    by_questions = sorted(entries, key=lambda item: item["total_solved"], reverse=True)
    by_rating = sorted(entries, key=lambda item: item["lc_rating"], reverse=True)
    by_college = build_college_leaderboard_data(entries)

    def assign_ranks(sorted_list, key):
        for index, entry in enumerate(sorted_list):
            entry[f"rank_{key}"] = index + 1
        return sorted_list

    assign_ranks(by_cscore, "cscore")
    assign_ranks(by_questions, "questions")
    assign_ranks(by_rating, "rating")
    assign_ranks(by_college, "college")

    current_user_id = str(current_user.id) if current_user.is_authenticated else None
    
    # Find current user's rank in each category
    current_user_rank = None
    if current_user_id:
        for i, entry in enumerate(by_cscore):
            if entry.get("user_id") == current_user_id:
                current_user_rank = i + 1
                break
    
    return render_template(
        "leaderboard.html",
        by_cscore=by_cscore,
        by_questions=by_questions,
        by_rating=by_rating,
        by_college=by_college,
        current_user_id=current_user_id,
        current_user_rank=current_user_rank,
    )


@leaderboard_bp.route("/api/leaderboard")
@cache.cached(timeout=300, query_string=True)
def api_leaderboard():
    mode = request.args.get("mode", "cscore")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    
    entries = build_leaderboard_data()

    if mode == "questions":
        entries.sort(key=lambda item: item["total_solved"], reverse=True)
    elif mode == "rating":
        entries.sort(key=lambda item: item["lc_rating"], reverse=True)
    elif mode == "college":
        entries = build_college_leaderboard_data(entries)
    else:
        entries.sort(key=lambda item: item["c_score"], reverse=True)

    # Assign ranks
    for index, entry in enumerate(entries):
        entry["rank"] = index + 1

    # Pagination
    total = len(entries)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_entries = entries[start:end]
    
    # Find current user's rank (for frontend to pin)
    current_user_id = request.args.get("current_user_id")
    current_user_rank = None
    if current_user_id:
        for entry in entries:
            if entry.get("user_id") == current_user_id:
                current_user_rank = entry["rank"]
                break

    return jsonify({
        "entries": paginated_entries,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "current_user_rank": current_user_rank
    })