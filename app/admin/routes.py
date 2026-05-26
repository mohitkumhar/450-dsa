import math
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask import session
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
QUESTION_DIFFICULTIES = ("Easy", "Medium", "Hard")
QUESTION_SORT = [("position", 1), ("_id", 1)]


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tail_file(file_path, max_lines=80):
    with file_path.open("r", encoding="utf-8", errors="replace") as file_obj:
        return list(deque(file_obj, maxlen=max_lines))


def _actor_label():
    return current_user.name or current_user.email or str(current_user.id)


def _write_admin_content_history(entity_type, entity_id, action, before=None, after=None):
    db.admin_content_history.insert_one(
        {
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "action": action,
            "before": before or {},
            "after": after or {},
            "actor_user_id": str(current_user.id),
            "actor_label": _actor_label(),
            "created_at": datetime.now(timezone.utc),
        }
    )


def _format_datetime(value):
    if hasattr(value, "astimezone"):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "-"


def _recent_error_logs(max_entries=120):
    root_dir = Path(__file__).resolve().parents[2]
    candidates = [
        root_dir / "logs" / "error.log",
        root_dir / "logs" / "app.log",
        root_dir / "instance" / "error.log",
        root_dir / "instance" / "app.log",
    ]

    existing = [file_path for file_path in candidates if file_path.is_file()]

    existing.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    entries = []
    per_file_limit = max(10, max_entries // max(1, len(existing)))
    for file_path in existing:
        try:
            lines = _tail_file(file_path, max_lines=per_file_limit)
        except OSError:
            continue
        rel_path = file_path.relative_to(root_dir).as_posix()
        for line in lines:
            text = line.rstrip("\n")
            if not text:
                continue
            entries.append({"source": rel_path, "line": text})
            if len(entries) >= max_entries:
                return entries

    return entries


def _compute_system_stats():
    total_users = db.user.count_documents({})

    total_submissions = 0
    active_users_today = set()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    projection = {"progress": 1, "external_totals": 1, "external_daily_counts": 1}
    for user in db.user.find({}, projection):
        progress = user.get("progress") or {}
        solved_in_app = 0

        for progress_item in progress.values():
            if progress_item.get("done"):
                solved_in_app += 1
                solved_at = progress_item.get("timestamp")
                if solved_at and hasattr(solved_at, "strftime") and solved_at.strftime("%Y-%m-%d") == today:
                    active_users_today.add(user["_id"])

        external_totals = user.get("external_totals") or {}
        external_solved = sum(
            max(external_totals.get(key, 0), 0)
            for key in ("LeetCode", "GFG", "Coding Ninjas", "HackerRank")
        )

        daily_counts = user.get("external_daily_counts") or {}
        if daily_counts.get(today, 0) > 0:
            active_users_today.add(user["_id"])

        total_submissions += solved_in_app + external_solved

    return {
        "total_users": total_users,
        "total_submissions": total_submissions,
        "active_users_today": len(active_users_today),
    }


def _build_user_query(search_term):
    search_term = (search_term or "").strip()
    if not search_term:
        return {}
    pattern = {"$regex": re.escape(search_term), "$options": "i"}
    return {"$or": [{"name": pattern}, {"email": pattern}]}


def _question_payload_from_form(form_data):
    problem = (form_data.get("problem") or "").strip()
    url = (form_data.get("url") or "").strip()
    url2 = (form_data.get("url2") or "").strip()
    difficulty = (form_data.get("difficulty") or "Medium").strip()
    topic_id = (form_data.get("topic_id") or "").strip()
    position_raw = (form_data.get("position") or "").strip()

    errors = []
    if not problem:
        errors.append("Problem title is required.")
    if not url:
        errors.append("Primary URL is required.")
    if difficulty not in QUESTION_DIFFICULTIES:
        errors.append("Difficulty must be Easy, Medium, or Hard.")
    if not ObjectId.is_valid(topic_id):
        errors.append("A valid topic is required.")
    try:
        position = int(position_raw)
        if position < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Position must be a non-negative integer.")
        position = 0

    payload = {
        "problem": problem,
        "url": url,
        "url2": url2,
        "difficulty": difficulty,
        "topic": ObjectId(topic_id) if ObjectId.is_valid(topic_id) else None,
        "position": position,
    }
    return payload, errors


def _topic_payload_from_form(form_data):
    name = (form_data.get("name") or "").strip()
    position_raw = (form_data.get("position") or "").strip()
    errors = []
    if not name:
        errors.append("Topic name is required.")
    try:
        position = int(position_raw)
        if position < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Topic position must be a non-negative integer.")
        position = 0
    return {"name": name, "position": position}, errors


def _topic_choices():
    return list(db.topic.find({}, {"name": 1, "position": 1}).sort("position", 1))


def _question_projection():
    return {"problem": 1, "url": 1, "url2": 1, "difficulty": 1, "topic": 1, "position": 1}


def _recent_content_history(limit=12):
    history = list(
        db.admin_content_history.find(
            {},
            {"entity_type": 1, "entity_id": 1, "action": 1, "actor_label": 1, "created_at": 1, "after": 1},
        )
        .sort("created_at", -1)
        .limit(limit)
    )
    for entry in history:
        entry["created_at_display"] = _format_datetime(entry.get("created_at"))
    return history


@admin_bp.route("", methods=["GET"])
@login_required
@admin_required
def dashboard():
    search_term = request.args.get("q", "").strip()
    page = max(_safe_int(request.args.get("page", 1), 1), 1)
    per_page = 10
    query_filter = _build_user_query(search_term)

    total_matching = db.user.count_documents(query_filter)
    total_pages = max(math.ceil(total_matching / per_page), 1)
    if page > total_pages:
        page = total_pages

    skip = (page - 1) * per_page
    projection = {"name": 1, "email": 1, "is_admin": 1, "created_at": 1}
    users = list(
        db.user.find(query_filter, projection)
        .sort("_id", -1)
        .skip(skip)
        .limit(per_page)
    )

    stats = _compute_system_stats()
    logs = _recent_error_logs(max_entries=80)

    return render_template(
        "admin/dashboard.html",
        users=users,
        search_term=search_term,
        page=page,
        per_page=per_page,
        total_matching=total_matching,
        total_pages=total_pages,
        stats=stats,
        logs=logs,
    )


@admin_bp.route("/questions", methods=["GET"])
@login_required
@admin_required
def question_manager():
    search_term = request.args.get("q", "").strip()
    topic_filter = request.args.get("topic", "").strip()

    query = {}
    if search_term:
        query["problem"] = {"$regex": re.escape(search_term), "$options": "i"}
    if topic_filter and ObjectId.is_valid(topic_filter):
        query["topic"] = ObjectId(topic_filter)

    questions = list(db.question.find(query, _question_projection()).sort(QUESTION_SORT))
    topics = _topic_choices()
    topic_lookup = {topic["_id"]: topic.get("name", "Unknown Topic") for topic in topics}
    for question in questions:
        question["topic_name"] = topic_lookup.get(question.get("topic"), "Unknown Topic")

    return render_template(
        "admin/questions.html",
        questions=questions,
        topics=topics,
        topic_filter=topic_filter,
        search_term=search_term,
        history_entries=_recent_content_history(),
    )


@admin_bp.route("/questions/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_question():
    topics = _topic_choices()
    form_values = {"problem": "", "url": "", "url2": "", "difficulty": "Medium", "topic_id": "", "position": "0"}

    if request.method == "POST":
        form_values.update(request.form)
        payload, errors = _question_payload_from_form(request.form)
        if not errors:
            result = db.question.insert_one(payload)
            _write_admin_content_history("question", result.inserted_id, "created", after={**payload, "topic": str(payload["topic"])})
            flash("Question created.", "success")
            return redirect(url_for("admin.question_manager"))
        for error in errors:
            flash(error, "danger")

    return render_template("admin/question_form.html", form_values=form_values, topics=topics, mode="create")


@admin_bp.route("/questions/<question_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_question(question_id):
    if not ObjectId.is_valid(question_id):
        flash("Invalid question id.", "danger")
        return redirect(url_for("admin.question_manager"))

    question = db.question.find_one({"_id": ObjectId(question_id)}, _question_projection())
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for("admin.question_manager"))

    topics = _topic_choices()
    form_values = {
        "problem": question.get("problem", ""),
        "url": question.get("url", ""),
        "url2": question.get("url2", ""),
        "difficulty": question.get("difficulty", "Medium"),
        "topic_id": str(question.get("topic") or ""),
        "position": str(question.get("position", 0)),
    }

    if request.method == "POST":
        form_values.update(request.form)
        payload, errors = _question_payload_from_form(request.form)
        if not errors:
            before = {
                "problem": question.get("problem", ""),
                "url": question.get("url", ""),
                "url2": question.get("url2", ""),
                "difficulty": question.get("difficulty", "Medium"),
                "topic": str(question.get("topic") or ""),
                "position": question.get("position", 0),
            }
            db.question.update_one({"_id": question["_id"]}, {"$set": payload})
            _write_admin_content_history("question", question["_id"], "updated", before=before, after={**payload, "topic": str(payload["topic"])})
            flash("Question updated.", "success")
            return redirect(url_for("admin.question_manager"))
        for error in errors:
            flash(error, "danger")

    return render_template("admin/question_form.html", form_values=form_values, topics=topics, mode="edit", question_id=question_id)


@admin_bp.route("/questions/<question_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_question(question_id):
    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        abort(400)
    if not ObjectId.is_valid(question_id):
        flash("Invalid question id.", "danger")
        return redirect(url_for("admin.question_manager"))
    question = db.question.find_one({"_id": ObjectId(question_id)}, _question_projection())
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for("admin.question_manager"))
    db.question.delete_one({"_id": question["_id"]})
    _write_admin_content_history(
        "question",
        question["_id"],
        "deleted",
        before={
            "problem": question.get("problem", ""),
            "difficulty": question.get("difficulty", "Medium"),
            "topic": str(question.get("topic") or ""),
            "position": question.get("position", 0),
        },
    )
    flash("Question deleted.", "success")
    return redirect(url_for("admin.question_manager"))


@admin_bp.route("/topics/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_topic():
    form_values = {"name": "", "position": "0"}
    if request.method == "POST":
        form_values.update(request.form)
        payload, errors = _topic_payload_from_form(request.form)
        if not errors:
            result = db.topic.insert_one(payload)
            _write_admin_content_history("topic", result.inserted_id, "created", after=payload)
            flash("Topic created.", "success")
            return redirect(url_for("admin.question_manager"))
        for error in errors:
            flash(error, "danger")
    return render_template("admin/topic_form.html", form_values=form_values, mode="create")


@admin_bp.route("/topics/<topic_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_topic(topic_id):
    if not ObjectId.is_valid(topic_id):
        flash("Invalid topic id.", "danger")
        return redirect(url_for("admin.question_manager"))
    topic = db.topic.find_one({"_id": ObjectId(topic_id)}, {"name": 1, "position": 1})
    if not topic:
        flash("Topic not found.", "danger")
        return redirect(url_for("admin.question_manager"))
    form_values = {"name": topic.get("name", ""), "position": str(topic.get("position", 0))}
    if request.method == "POST":
        form_values.update(request.form)
        payload, errors = _topic_payload_from_form(request.form)
        if not errors:
            before = {"name": topic.get("name", ""), "position": topic.get("position", 0)}
            db.topic.update_one({"_id": topic["_id"]}, {"$set": payload})
            _write_admin_content_history("topic", topic["_id"], "updated", before=before, after=payload)
            flash("Topic updated.", "success")
            return redirect(url_for("admin.question_manager"))
        for error in errors:
            flash(error, "danger")
    return render_template("admin/topic_form.html", form_values=form_values, mode="edit", topic_id=topic_id)


@admin_bp.route("/topics/<topic_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_topic(topic_id):
    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        abort(400)
    if not ObjectId.is_valid(topic_id):
        flash("Invalid topic id.", "danger")
        return redirect(url_for("admin.question_manager"))
    topic = db.topic.find_one({"_id": ObjectId(topic_id)}, {"name": 1, "position": 1})
    if not topic:
        flash("Topic not found.", "danger")
        return redirect(url_for("admin.question_manager"))
    if db.question.count_documents({"topic": topic["_id"]}) > 0:
        flash("Delete or move the topic's questions before deleting the topic.", "warning")
        return redirect(url_for("admin.question_manager"))
    db.topic.delete_one({"_id": topic["_id"]})
    _write_admin_content_history("topic", topic["_id"], "deleted", before={"name": topic.get("name", ""), "position": topic.get("position", 0)})
    flash("Topic deleted.", "success")
    return redirect(url_for("admin.question_manager"))


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    search_term = (request.form.get("q") or request.args.get("q") or "").strip()
    page = max(_safe_int(request.form.get("page") or request.args.get("page"), 1), 1)

    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        abort(400)

    if not ObjectId.is_valid(user_id):
        flash("Invalid user id.", "danger")
        return redirect(url_for("admin.dashboard", q=search_term, page=page))

    target_id = ObjectId(user_id)
    if str(current_user.id) == str(target_id):
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("admin.dashboard", q=search_term, page=page))

    target_user = db.user.find_one({"_id": target_id}, {"name": 1, "email": 1})
    if not target_user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.dashboard", q=search_term, page=page))

    result = db.user.delete_one({"_id": target_id})
    if result.deleted_count != 1:
        abort(500)

    display_name = target_user.get("name") or target_user.get("email") or "user"
    flash(f"Deleted account for {display_name}.", "success")
    return redirect(url_for("admin.dashboard", q=search_term, page=page))
