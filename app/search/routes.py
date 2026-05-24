from flask import Blueprint, jsonify, render_template, request

from app.extensions import limiter
from app.utils import search_dsa_questions


search_bp = Blueprint("search", __name__)


@search_bp.route("/search")
def search():
    initial_query = request.args.get("q", "").strip()
    return render_template("search.html", initial_query=initial_query)


@search_bp.route("/api/search_questions")
@limiter.limit("30 per minute")
def api_search_questions():
    """Search DSA questions.
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
        limit = min(max(int(request.args.get("limit", 40)), 1), 80)
    except ValueError:
        limit = 40

    payload = search_dsa_questions(raw_query, limit=limit)
    return jsonify(payload)
