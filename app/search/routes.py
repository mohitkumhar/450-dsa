from bson import ObjectId
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user

from app.extensions import db, limiter
from app.utils import json_error, json_success, utc_now
from app.search.service import search_dsa_questions


search_bp = Blueprint("search", __name__)

DEFAULT_SEARCH_LIMIT = 40
MAX_SEARCH_LIMIT = 80


def normalize_saved_search_text(value):
    return " ".join((value or "").strip().split())


def normalize_saved_search_filters(filters):
    filters = filters if isinstance(filters, dict) else {}
    normalized = {}
    for key in ("topic_id", "difficulty", "platform", "status"):
        value = normalize_saved_search_text(filters.get(key, ""))
        normalized[key] = value.lower() if key != "topic_id" else value
    return normalized


def summarize_saved_search(query, filters):
    parts = []
    if query:
        parts.append(query)
    for label, key in (("Topic", "topic_id"), ("Difficulty", "difficulty"), ("Platform", "platform"), ("Status", "status")):
        value = filters.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return " · ".join(parts) or "Saved search"


def serialize_saved_search(entry):
    filters = normalize_saved_search_filters(entry.get("filters"))
    query = normalize_saved_search_text(entry.get("query", ""))
    name = normalize_saved_search_text(entry.get("name", "")) or summarize_saved_search(query, filters)
    return {
        "id": str(entry.get("id", "")),
        "query": query,
        "filters": filters,
        "name": name,
    }


def get_saved_searches(user_doc):
    return [serialize_saved_search(entry) for entry in (user_doc.get("saved_searches") or []) if isinstance(entry, dict)]


def find_saved_search_index(saved_searches, search_id):
    for index, entry in enumerate(saved_searches):
        if str(entry.get("id", "")) == search_id:
            return index
    return None


@search_bp.route("/search")
def search():
    initial_query = request.args.get("q", "").strip()
    pre = current_app.config.get("_PRECOMPUTED")
    if pre:
        topics = [{"name": t["name"], "_id": t["_id"]} for t in pre["topics"]]
    else:
        try:
            topics = list(db.topic.find({}, {"name": 1}).sort("position", 1))
        except Exception:
            topics = []
    saved_searches = get_saved_searches(current_user._get_current_object()) if current_user.is_authenticated else []
    return render_template(
        "search.html",
        initial_query=initial_query,
        topics=topics,
        saved_searches=saved_searches,
    )


@search_bp.route("/api/saved_searches", methods=["POST"])
def save_search_query():
    if not current_user.is_authenticated:
        return json_error("Login required", status_code=401)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Request body must be a JSON object", status_code=400)

    query = normalize_saved_search_text(data.get("query", ""))
    filters = normalize_saved_search_filters(data.get("filters"))
    name = normalize_saved_search_text(data.get("name", "")) or summarize_saved_search(query, filters)
    if not query and not any(filters.values()):
        return json_error("Search query cannot be empty", status_code=400)

    user_doc = db.user.find_one({"_id": current_user.id}) or {}
    saved_searches = list(user_doc.get("saved_searches") or [])
    new_key = {"query": query.lower(), "filters": filters}
    now = utc_now()

    match_index = None
    for index, entry in enumerate(saved_searches):
        if not isinstance(entry, dict):
            continue
        existing_key = {
            "query": normalize_saved_search_text(entry.get("query", "")).lower(),
            "filters": normalize_saved_search_filters(entry.get("filters")),
        }
        if existing_key == new_key:
            match_index = index
            break

    if match_index is not None:
        saved_searches[match_index].update({"name": name, "updated_at": now})
    else:
        saved_searches.insert(
            0,
            {
                "id": str(ObjectId()),
                "query": query,
                "filters": filters,
                "name": name,
                "created_at": now,
                "updated_at": now,
            },
        )

    db.user.update_one({"_id": current_user.id}, {"$set": {"saved_searches": saved_searches}})
    current_user.reload()
    return json_success(message="Saved search stored", saved_searches=get_saved_searches(current_user._get_current_object()))


@search_bp.route("/api/saved_searches/<search_id>", methods=["PATCH", "DELETE"])
def update_saved_search_query(search_id):
    if not current_user.is_authenticated:
        return json_error("Login required", status_code=401)

    user_doc = db.user.find_one({"_id": current_user.id}) or {}
    saved_searches = list(user_doc.get("saved_searches") or [])
    index = find_saved_search_index(saved_searches, search_id)
    if index is None:
        return json_error("Saved search not found", status_code=404)

    if request.method == "DELETE":
        saved_searches.pop(index)
    else:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("Request body must be a JSON object", status_code=400)
        name = normalize_saved_search_text(data.get("name", ""))
        if not name:
            return json_error("name is required", status_code=400)
        saved_searches[index]["name"] = name
        saved_searches[index]["updated_at"] = utc_now()

    db.user.update_one({"_id": current_user.id}, {"$set": {"saved_searches": saved_searches}})
    current_user.reload()
    return json_success(
        message="Saved searches updated",
        saved_searches=get_saved_searches(current_user._get_current_object()),
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
