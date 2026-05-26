import math
import re
import csv
import io
import json
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
IMPORT_PREVIEW_SESSION_KEY = "admin_sheet_import_preview"


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tail_file(file_path, max_lines=80):
    with file_path.open("r", encoding="utf-8", errors="replace") as file_obj:
        return list(deque(file_obj, maxlen=max_lines))


def _load_import_records_from_upload(file_storage):
    filename = (file_storage.filename or "").strip().lower()
    raw_text = file_storage.read().decode("utf-8")
    if filename.endswith(".json"):
        return "json", json.loads(raw_text)
    if filename.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(raw_text))
        return "csv", list(reader)
    raise ValueError("Only .json and .csv sheet uploads are supported.")


def _normalize_import_rows(kind, payload):
    if kind == "json":
        rows = []
        for topic in payload:
            topic_name = (topic.get("topicName") or "").strip()
            topic_position = topic.get("position", 0)
            for question_position, question in enumerate(topic.get("questions") or []):
                rows.append(
                    {
                        "topic_name": topic_name,
                        "topic_position": topic_position,
                        "problem": (question.get("Problem") or "").strip(),
                        "url": (question.get("URL") or "").strip(),
                        "url2": (question.get("URL2") or "").strip(),
                        "difficulty": (question.get("difficulty") or "Medium").strip(),
                        "position": question.get("position", question_position),
                    }
                )
        return rows

    rows = []
    for row in payload:
        rows.append(
            {
                "topic_name": (row.get("topic_name") or row.get("topic") or "").strip(),
                "topic_position": row.get("topic_position", 0),
                "problem": (row.get("problem") or "").strip(),
                "url": (row.get("url") or "").strip(),
                "url2": (row.get("url2") or "").strip(),
                "difficulty": (row.get("difficulty") or "Medium").strip(),
                "position": row.get("position", 0),
            }
        )
    return rows


def _build_import_preview(rows):
    errors = []
    normalized_rows = []
    seen_topics = {}
    seen_questions = set()

    for index, row in enumerate(rows, start=1):
        topic_name = row.get("topic_name", "").strip()
        problem = row.get("problem", "").strip()
        url = row.get("url", "").strip()
        url2 = row.get("url2", "").strip()
        difficulty = row.get("difficulty", "Medium").strip()

        try:
            topic_position = int(row.get("topic_position", 0))
            if topic_position < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"Row {index}: topic_position must be a non-negative integer.")
            topic_position = 0

        try:
            position = int(row.get("position", 0))
            if position < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"Row {index}: position must be a non-negative integer.")
            position = 0

        if not topic_name:
            errors.append(f"Row {index}: topic_name is required.")
        if not problem:
            errors.append(f"Row {index}: problem is required.")
        if not url:
            errors.append(f"Row {index}: url is required.")
        if difficulty not in QUESTION_DIFFICULTIES:
            errors.append(f"Row {index}: difficulty must be Easy, Medium, or Hard.")
        if url and not re.match(r"^https?://", url):
            errors.append(f"Row {index}: url must start with http:// or https://.")
        if url2 and not re.match(r"^https?://", url2):
            errors.append(f"Row {index}: url2 must start with http:// or https://.")

        topic_key = topic_name.lower()
        if topic_key in seen_topics and seen_topics[topic_key] != topic_position:
            errors.append(f"Row {index}: topic '{topic_name}' uses conflicting topic_position values.")
        seen_topics.setdefault(topic_key, topic_position)

        duplicate_key = (topic_key, problem.lower(), url.lower())
        if duplicate_key in seen_questions:
            errors.append(f"Row {index}: duplicate question row detected for '{problem}'.")
        seen_questions.add(duplicate_key)

        normalized_rows.append(
            {
                "topic_name": topic_name,
                "topic_position": topic_position,
                "problem": problem,
                "url": url,
                "url2": url2,
                "difficulty": difficulty,
                "position": position,
            }
        )

    preview_topics = []
    for topic_name_key, topic_position in sorted(seen_topics.items(), key=lambda item: item[1]):
        topic_name = next(row["topic_name"] for row in normalized_rows if row["topic_name"].lower() == topic_name_key)
        preview_topics.append({"name": topic_name, "position": topic_position})

    return {
        "rows": normalized_rows,
        "errors": errors,
        "topics": preview_topics,
        "question_count": len(normalized_rows),
        "topic_count": len(preview_topics),
    }


def _commit_import_preview(preview):
    inserted_topic_ids = []
    inserted_question_ids = []
    topic_ids = {}

    try:
        for topic in preview["topics"]:
            existing = db.topic.find_one({"name": topic["name"]}, {"_id": 1})
            if existing:
                db.topic.update_one({"_id": existing["_id"]}, {"$set": {"position": topic["position"]}})
                topic_ids[topic["name"].lower()] = existing["_id"]
            else:
                result = db.topic.insert_one({"name": topic["name"], "position": topic["position"]})
                inserted_topic_ids.append(result.inserted_id)
                topic_ids[topic["name"].lower()] = result.inserted_id

        question_docs = []
        for row in preview["rows"]:
            question_docs.append(
                {
                    "topic": topic_ids[row["topic_name"].lower()],
                    "problem": row["problem"],
                    "url": row["url"],
                    "url2": row["url2"],
                    "difficulty": row["difficulty"],
                    "position": row["position"],
                }
            )

        if question_docs:
            result = db.question.insert_many(question_docs)
            inserted_question_ids.extend(result.inserted_ids)
    except Exception:
        if inserted_question_ids:
            db.question.delete_many({"_id": {"$in": inserted_question_ids}})
        if inserted_topic_ids:
            db.topic.delete_many({"_id": {"$in": inserted_topic_ids}})
        raise


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


@admin_bp.route("/import-sheet", methods=["GET", "POST"])
@login_required
@admin_required
def import_sheet():
    preview = session.get(IMPORT_PREVIEW_SESSION_KEY)
    if request.method == "POST":
        file_storage = request.files.get("sheet_file")
        if not file_storage or not file_storage.filename:
            flash("Upload a JSON or CSV sheet file first.", "danger")
            return render_template("admin/import_sheet.html", preview=preview)

        try:
            kind, payload = _load_import_records_from_upload(file_storage)
            rows = _normalize_import_rows(kind, payload)
            preview = _build_import_preview(rows)
            session[IMPORT_PREVIEW_SESSION_KEY] = preview
        except Exception as exc:
            preview = None
            session.pop(IMPORT_PREVIEW_SESSION_KEY, None)
            flash(f"Import preview failed: {exc}", "danger")

    return render_template("admin/import_sheet.html", preview=preview)


@admin_bp.route("/import-sheet/confirm", methods=["POST"])
@login_required
@admin_required
def confirm_import_sheet():
    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        abort(400)

    preview = session.get(IMPORT_PREVIEW_SESSION_KEY)
    if not preview:
        flash("No validated import preview found. Upload a sheet first.", "warning")
        return redirect(url_for("admin.import_sheet"))
    if preview.get("errors"):
        flash("Fix the preview errors before importing.", "danger")
        return redirect(url_for("admin.import_sheet"))

    _commit_import_preview(preview)
    session.pop(IMPORT_PREVIEW_SESSION_KEY, None)
    flash(
        f"Imported {preview['question_count']} questions across {preview['topic_count']} topics.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


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
