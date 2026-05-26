import secrets

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db, limiter
from app.search.service import search_dsa_questions


search_bp = Blueprint("search", __name__)
MAX_SAVED_SEARCHES = 12


def _json_response(payload=None, status_code=200, **fields):
    body = dict(payload or {})
    body.update(fields)
    response = jsonify(body)
    return response if status_code == 200 else (response, status_code)


def _json_success(status_code=200, **fields):
    return _json_response({"success": True}, status_code=status_code, **fields)


def _json_error(error, status_code=400, **fields):
    return _json_response({"success": False, "error": error}, status_code=status_code, **fields)


def _sanitize_saved_searches(saved_searches):
    sanitized = []
    for entry in saved_searches or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "").strip()
        query = " ".join(str(entry.get("query") or "").split())
        name = " ".join(str(entry.get("name") or "").split())
        if not entry_id or not query:
            continue
        sanitized.append(
            {
                "id": entry_id,
                "name": name or query,
                "query": query,
            }
        )
    return sanitized


def _saved_searches_for_current_user():
    if not current_user.is_authenticated:
        return []
    return _sanitize_saved_searches(getattr(current_user, "saved_searches", []))


@search_bp.route("/search")
def search():
    initial_query = request.args.get("q", "").strip()
    return render_template(
        "search.html",
        initial_query=initial_query,
        saved_searches=_saved_searches_for_current_user(),
    )


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
        limit = min(max(int(request.args.get("limit", 40)), 1), 80)
    except ValueError:
        limit = 40

    payload = search_dsa_questions(raw_query, limit=limit)
    return jsonify(payload)


@search_bp.route("/api/saved_searches", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def create_saved_search():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error("Request body must be a JSON object")

    query = " ".join(str(data.get("query") or "").split())
    name = " ".join(str(data.get("name") or "").split()) or query
    if not query:
        return _json_error("query is required")

    saved_searches = _saved_searches_for_current_user()
    if len(saved_searches) >= MAX_SAVED_SEARCHES:
        return _json_error(f"You can save up to {MAX_SAVED_SEARCHES} searches.")

    saved_searches.insert(
        0,
        {
            "id": secrets.token_hex(8),
            "name": name[:80],
            "query": query,
        },
    )
    db.user.update_one({"_id": current_user.id}, {"$set": {"saved_searches": saved_searches}})
    current_user.reload()
    return _json_success(saved_searches=saved_searches)


@search_bp.route("/api/saved_searches/<search_id>", methods=["PATCH"])
@login_required
@limiter.limit("30 per minute")
def rename_saved_search(search_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error("Request body must be a JSON object")

    new_name = " ".join(str(data.get("name") or "").split())
    if not new_name:
        return _json_error("name is required")

    saved_searches = _saved_searches_for_current_user()
    updated = False
    for entry in saved_searches:
        if entry["id"] == search_id:
            entry["name"] = new_name[:80]
            updated = True
            break

    if not updated:
        return _json_error("Saved search not found", status_code=404)

    db.user.update_one({"_id": current_user.id}, {"$set": {"saved_searches": saved_searches}})
    current_user.reload()
    return _json_success(saved_searches=saved_searches)


@search_bp.route("/api/saved_searches/<search_id>", methods=["DELETE"])
@login_required
@limiter.limit("30 per minute")
def delete_saved_search(search_id):
    saved_searches = _saved_searches_for_current_user()
    next_saved_searches = [entry for entry in saved_searches if entry["id"] != search_id]
    if len(next_saved_searches) == len(saved_searches):
        return _json_error("Saved search not found", status_code=404)

    db.user.update_one({"_id": current_user.id}, {"$set": {"saved_searches": next_saved_searches}})
    current_user.reload()
    return _json_success(saved_searches=next_saved_searches)
