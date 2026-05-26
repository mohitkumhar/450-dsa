from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from app.extensions import limiter, cache
from app.leaderboard.cache import LEADERBOARD_CACHE_TIMEOUT, api_leaderboard_cache_key, leaderboard_page_cache_key
from app.leaderboard.service import (
    build_college_leaderboard_data,
    build_leaderboard_data,
    get_user_rank_by_c_score,
    sort_leaderboard_entries_by_c_score,
)


leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard")
@limiter.limit("20 per minute")
@cache.cached(timeout=LEADERBOARD_CACHE_TIMEOUT, make_cache_key=leaderboard_page_cache_key)
def leaderboard():
    entries = build_leaderboard_data()

    by_cscore = sort_leaderboard_entries_by_c_score(entries)
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
    current_user_rank = get_user_rank_by_c_score(current_user_id, by_cscore)
    
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
@cache.cached(timeout=LEADERBOARD_CACHE_TIMEOUT, make_cache_key=api_leaderboard_cache_key)
def api_leaderboard():
    """Return paginated leaderboard rankings for the selected mode.
    ---
    tags:
      - Leaderboard
    parameters:
      - name: mode
        in: query
        type: string
        required: false
        default: cscore
        enum:
          - cscore
          - questions
          - rating
          - college
        description: Ranking mode used to sort leaderboard entries.
      - name: page
        in: query
        type: integer
        required: false
        default: 1
        minimum: 1
        description: Page number for paginated results.
      - name: per_page
        in: query
        type: integer
        required: false
        default: 20
        maximum: 100
        description: Number of entries per page.
      - name: current_user_id
        in: query
        type: string
        required: false
        description: Optional user id used to return that user's current rank.
    responses:
      200:
        description: Paginated leaderboard response.
        schema:
          type: object
          properties:
            entries:
              type: array
              items:
                type: object
                properties:
                  rank:
                    type: integer
                  user_id:
                    type: string
                  name:
                    type: string
                  profile_photo:
                    type: string
                  college:
                    type: string
                  c_score:
                    type: integer
                  total_solved:
                    type: integer
                  dsa_done:
                    type: integer
                  lc_total:
                    type: integer
                  lc_rating:
                    type: integer
            total:
              type: integer
            page:
              type: integer
            per_page:
              type: integer
            total_pages:
              type: integer
            current_user_rank:
              type: integer
              x-nullable: true
    """
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
