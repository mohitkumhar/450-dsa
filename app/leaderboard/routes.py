from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from app.extensions import limiter, cache
from app.leaderboard.service import (
    get_leaderboard_snapshot,
)


leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard")
@limiter.limit("20 per minute")
@cache.cached(timeout=300)
def leaderboard():
    by_cscore = get_leaderboard_snapshot("cscore")
    by_questions = get_leaderboard_snapshot("questions")
    by_rating = get_leaderboard_snapshot("rating")
    by_college = get_leaderboard_snapshot("college")

    for entry in by_cscore:
        entry["rank_cscore"] = entry["rank"]
    for entry in by_questions:
        entry["rank_questions"] = entry["rank"]
    for entry in by_rating:
        entry["rank_rating"] = entry["rank"]
    for entry in by_college:
        entry["rank_college"] = entry["rank"]

    current_user_id = str(current_user.id) if current_user.is_authenticated else None
    
    # Find current user's rank in each category
    current_user_rank = None
    if current_user_id:
        for entry in by_cscore:
            if entry.get("user_id") == current_user_id:
                current_user_rank = entry["rank"]
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
    
    entries = get_leaderboard_snapshot(mode)

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
