from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from app.extensions import db
from app.utils import json_error, json_success, json_response, utc_now

mylist_bp = Blueprint("mylist", __name__, url_prefix="/mylist")

VALID_DIFFICULTIES = ("Easy", "Medium", "Hard")

def _owned(doc):
    return doc and str(doc.get("owner")) == str(current_user.id)

@mylist_bp.route("/")
@login_required
def index():
    questions = list(db.user_questions.find({"owner": current_user.id}).sort("created_at", -1))
    return render_template("mylist.html", questions=questions)

@mylist_bp.route("/add", methods=["POST"])
@login_required
def add_question():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Invalid request body", 400)
    title = (data.get("title") or "").strip()
    if not title:
        return json_error("Title is required", 400)
    difficulty = data.get("difficulty", "Medium")
    if difficulty not in VALID_DIFFICULTIES:
        return json_error("difficulty must be Easy, Medium or Hard", 400)
    doc = {
        "owner": current_user.id,
        "title": title,
        "url": (data.get("url") or "").strip(),
        "category": (data.get("category") or "").strip(),
        "difficulty": difficulty,
        "notes": (data.get("notes") or "").strip(),
        "done": False,
        "created_at": utc_now(),
    }
    result = db.user_questions.insert_one(doc)
    return json_response({"success": True, "id": str(result.inserted_id)}, 201)

@mylist_bp.route("/<question_id>", methods=["PATCH"])
@login_required
def update_question(question_id):
    try:
        oid = ObjectId(question_id)
    except InvalidId:
        return json_error("Not found", 404)
    doc = db.user_questions.find_one({"_id": oid})
    if not _owned(doc):
        return json_error("Not found", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Invalid request body", 400)
    fields = {}
    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return json_error("Title is required", 400)
        fields["title"] = title
    if "url" in data:
        fields["url"] = (data["url"] or "").strip()
    if "category" in data:
        fields["category"] = (data["category"] or "").strip()
    if "difficulty" in data:
        if data["difficulty"] not in VALID_DIFFICULTIES:
            return json_error("difficulty must be Easy, Medium or Hard", 400)
        fields["difficulty"] = data["difficulty"]
    if "notes" in data:
        fields["notes"] = (data["notes"] or "").strip()
    if "done" in data:
        if not isinstance(data["done"], bool):
            return json_error("done must be a boolean", 400)
        fields["done"] = data["done"]
    if fields:
        db.user_questions.update_one({"_id": oid}, {"$set": fields})
    return json_success()

@mylist_bp.route("/<question_id>", methods=["DELETE"])
@login_required
def delete_question(question_id):
    try:
        oid = ObjectId(question_id)
    except InvalidId:
        return json_error("Not found", 404)
    doc = db.user_questions.find_one({"_id": oid})
    if not _owned(doc):
        return json_error("Not found", 404)
    db.user_questions.delete_one({"_id": oid})
    return json_success()
