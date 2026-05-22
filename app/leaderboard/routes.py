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
    return render_template(
        "leaderboard.html",
        by_cscore=by_cscore,
        by_questions=by_questions,
        by_rating=by_rating,
        by_college=by_college,
        current_user_id=current_user_id,
    )


@leaderboard_bp.route("/api/leaderboard")
@cache.cached(timeout=300, query_string=True)
def api_leaderboard():
    mode = request.args.get("mode", "cscore")
    entries = build_leaderboard_data()

    if mode == "questions":
        entries.sort(key=lambda item: item["total_solved"], reverse=True)
    elif mode == "rating":
        entries.sort(key=lambda item: item["lc_rating"], reverse=True)
    elif mode == "college":
        entries = build_college_leaderboard_data(entries)
    else:
        entries.sort(key=lambda item: item["c_score"], reverse=True)

    for index, entry in enumerate(entries):
        entry["rank"] = index + 1

    return jsonify(entries)
