from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from app.extensions import db, limiter
from app.search.service import search_dsa_questions


search_bp = Blueprint("search", __name__)

DEFAULT_SEARCH_LIMIT = 40
MAX_SEARCH_LIMIT = 80


@search_bp.route("/search")
def search():
    initial_query = request.args.get("q", "").strip()
    try:
        topics = list(db.topic.find({}, {"name": 1}).sort("position", 1))
    except Exception:
        topics = []
    return render_template("search.html", initial_query=initial_query, topics=topics)


@search_bp.route("/api/search_questions")
@limiter.limit("30 per minute")
def api_search_questions():
    """Return question search results and external search suggestions.
    ---
    tags:
      - Search
    parameters:
      - name: q
        in: query
        type: string
        required: false
        description: Search text. Supports platform filters such as "leetcode arrays".
      - name: limit
        in: query
        type: integer
        required: false
        default: 40
        minimum: 1
        maximum: 80
        description: Maximum number of matching questions to return.
    responses:
      200:
        description: Search results and external search suggestions.
        schema:
          type: object
          properties:
            query:
              type: string
            requested_platforms:
              type: array
              items:
                type: string
            results:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  problem:
                    type: string
                  topic:
                    type: string
                  topic_id:
                    type: string
                  links:
                    type: array
                    items:
                      type: object
                      properties:
                        platform:
                          type: string
                        url:
                          type: string
                        color:
                          type: string
                  external_searches:
                    type: array
                    items:
                      type: object
                  score:
                    type: integer
            external_searches:
              type: array
              items:
                type: object
      429:
        description: Rate limit exceeded.
    """
    raw_query = request.args.get("q", "")
    try:
        limit = min(max(int(request.args.get("limit", DEFAULT_SEARCH_LIMIT)), 1), MAX_SEARCH_LIMIT)
    except ValueError:
        limit = DEFAULT_SEARCH_LIMIT

    filters = {
        "topic_id": request.args.get("topic_id", "").strip(),
        "difficulty": request.args.get("difficulty", "").strip().lower(),
        "platform": request.args.get("platform", "").strip().lower(),
        "status": request.args.get("status", "").strip().lower(),
    }
    progress = current_user.progress if current_user.is_authenticated else {}
    payload = search_dsa_questions(raw_query, limit=limit, filters=filters, progress=progress)
    return jsonify(payload)
