from bson import ObjectId
from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.utils import utc_now
from notes_export import build_topic_notes_markdown, topic_notes_filename


tracker_bp = Blueprint("tracker", __name__)


@tracker_bp.route("/")
def index():
    topics = list(db.topic.find().sort("position", 1))
    total_questions = db.question.count_documents({})

    if current_user.is_authenticated:
        progress = current_user.progress
        done_questions = sum(1 for progress_item in progress.values() if progress_item.get("done"))
    else:
        progress = {}
        done_questions = 0

    all_questions = list(db.question.find())
    topic_question_count = {}
    for question in all_questions:
        topic_id = str(question["topic"])
        topic_question_count.setdefault(topic_id, []).append(str(question["_id"]))

    topic_progress = {}
    for topic in topics:
        topic_id = str(topic["_id"])
        topic_question_ids = topic_question_count.get(topic_id, [])
        if current_user.is_authenticated:
            topic_done = sum(1 for question_id in topic_question_ids if progress.get(question_id, {}).get("done"))
        else:
            topic_done = 0
        topic_progress[topic_id] = {"done": topic_done, "total": len(topic_question_ids)}

    return render_template(
        "index.html",
        topics=topics,
        total_questions=total_questions,
        done_questions=done_questions,
        topic_progress=topic_progress,
    )


@tracker_bp.route("/topic/<topic_id>")
def topic(topic_id):
    try:
        topic_doc = db.topic.find_one({"_id": ObjectId(topic_id)})
    except Exception:
        return "Topic not found", 404
    if not topic_doc:
        return "Topic not found", 404

    questions = list(db.question.find({"topic": topic_doc["_id"]}))
    
    # Get difficulty filter from query parameter
    difficulty_filter = request.args.get('difficulty', 'all')
    
    # Filter questions by difficulty if needed
    if difficulty_filter != 'all':
        questions = [q for q in questions if q.get('difficulty', 'Medium') == difficulty_filter]
    
    progress_dict = current_user.progress if current_user.is_authenticated else {}
    
    return render_template(
        "topic.html", 
        topic=topic_doc, 
        questions=questions, 
        progress_dict=progress_dict,
        difficulty_filter=difficulty_filter
    )


@tracker_bp.route("/topic/<topic_id>/export-notes")
@login_required
def export_topic_notes(topic_id):
    try:
        topic_doc = db.topic.find_one({"_id": ObjectId(topic_id)})
    except Exception:
        return "Topic not found", 404
    if not topic_doc:
        return "Topic not found", 404

    questions = list(db.question.find({"topic": topic_doc["_id"]}))
    markdown = build_topic_notes_markdown(topic_doc["name"], questions, current_user.progress)
    response = Response(markdown, mimetype="text/markdown")
    response.headers["Content-Disposition"] = f'attachment; filename={topic_notes_filename(topic_doc["name"])}'
    return response


@tracker_bp.route("/update_question/<question_id>", methods=["POST"])
@login_required
def update_question(question_id):
    try:
        question = db.question.find_one({"_id": ObjectId(question_id)})
    except Exception:
        return jsonify({"success": False, "error": "Question not found"}), 404
    if not question:
        return jsonify({"success": False, "error": "Question not found"}), 404

    data = request.json
    user_id = current_user.id
    update_fields = {}
    progress = current_user.progress
    existing = progress.get(question_id, {})

    if "done" in data:
        if data["done"] and not existing.get("done"):
            update_fields[f"progress.{question_id}.timestamp"] = utc_now()
        update_fields[f"progress.{question_id}.done"] = data["done"]
    if "bookmark" in data:
        update_fields[f"progress.{question_id}.bookmark"] = data["bookmark"]
    if "notes" in data:
        update_fields[f"progress.{question_id}.notes"] = data["notes"]

    if update_fields:
        db.user.update_one({"_id": user_id}, {"$set": update_fields})
        current_user.reload()

    return jsonify({"success": True})


@tracker_bp.route("/bookmarks")
@login_required
def bookmarks():
    progress = current_user.progress
    bookmarked_question_ids = [question_id for question_id, progress_item in progress.items() if progress_item.get("bookmark")]

    object_ids = []
    for question_id in bookmarked_question_ids:
        try:
            object_ids.append(ObjectId(question_id))
        except Exception:
            pass
    questions = list(db.question.find({"_id": {"$in": object_ids}}))

    topic_ids = list(set(question["topic"] for question in questions))
    topic_docs = {topic["_id"]: topic["name"] for topic in db.topic.find({"_id": {"$in": topic_ids}})}
    for question in questions:
        question["topic_name"] = topic_docs.get(question["topic"], "Unknown")

    return render_template("bookmarks.html", questions=questions, progress_dict=progress)


@tracker_bp.route("/export/csv")
@login_required
def export_csv():
    import csv
    from io import StringIO
    from flask import Response
    
    questions = list(db.question.find())
    topic_ids = list({q.get('topic') for q in questions if q.get('topic')})
    topic_lookup = {
        topic['_id']: topic.get('name', 'Unknown')
        for topic in db.topic.find({'_id': {'$in': topic_ids}}, {'name': 1})
    }
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Topic', 'Problem', 'Status', 'Bookmarked', 'Notes', 'Difficulty', 'URL', 'URL2'])
    
    for q in questions:
        topic_name = topic_lookup.get(q.get('topic'), 'Unknown')
        q_id = str(q['_id'])
        progress = current_user.progress.get(q_id, {})
        status = 'Done' if progress.get('done') else 'Pending'
        bookmarked = 'Yes' if progress.get('bookmark') else 'No'
        notes = progress.get('notes', '')
        difficulty = q.get('difficulty', 'Medium')
        
        writer.writerow([
            topic_name, q.get('problem', ''), status, bookmarked, 
            notes, difficulty, q.get('url', ''), q.get('url2', '')
        ])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=my_dsa_progress.csv'
    return response