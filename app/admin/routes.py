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


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tail_file(file_path, max_lines=80):
    with file_path.open("r", encoding="utf-8", errors="replace") as file_obj:
        return list(deque(file_obj, maxlen=max_lines))


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


def _build_admin_user_detail(user_doc):
    progress = user_doc.get("progress") or {}
    solved_items = {question_id: item for question_id, item in progress.items() if item.get("done")}
    all_questions = list(db.question.find({}, {"name": 1, "topic": 1, "url": 1}))
    stats = _compute_system_stats()
    _ = stats  # keep parity with existing admin route access patterns

    question_ids = []
    for question_id in solved_items:
        if ObjectId.is_valid(question_id):
            question_ids.append(ObjectId(question_id))

    questions = list(db.question.find({"_id": {"$in": question_ids}}, {"name": 1, "topic": 1}))
    question_map = {str(question["_id"]): question for question in questions}

    topic_ids = list({question.get("topic") for question in questions if question.get("topic")})
    topics = list(db.topic.find({"_id": {"$in": topic_ids}}, {"name": 1})) if topic_ids else []
    topic_map = {topic["_id"]: topic.get("name", "Unknown Topic") for topic in topics}

    recent_activity = []
    for question_id, item in solved_items.items():
        timestamp = item.get("timestamp")
        if not timestamp:
            continue
        question = question_map.get(question_id, {})
        recent_activity.append(
            {
                "question_name": question.get("name", "Question"),
                "topic_name": topic_map.get(question.get("topic"), "Unknown Topic"),
                "timestamp_display": _format_datetime(timestamp),
            }
        )
    recent_activity.sort(key=lambda entry: entry["timestamp_display"], reverse=True)

    external_totals = user_doc.get("external_totals") or {}
    platform_accounts = [
        {"label": "LeetCode", "username": user_doc.get("leetcode_username", ""), "total": external_totals.get("LeetCode", 0)},
        {"label": "GitHub", "username": user_doc.get("github_username", ""), "total": external_totals.get("GitHub_Commits", 0)},
        {"label": "GeeksforGeeks", "username": user_doc.get("gfg_username", ""), "total": external_totals.get("GFG", 0)},
        {"label": "Coding Ninjas", "username": user_doc.get("codingninjas_username", ""), "total": external_totals.get("Coding Ninjas", 0)},
        {"label": "HackerRank", "username": user_doc.get("hackerrank_username", ""), "total": external_totals.get("HackerRank", 0)},
        {"label": "AtCoder", "username": user_doc.get("atcoder_username", ""), "total": external_totals.get("AtCoder", 0)},
    ]

    bookmarks = sum(1 for item in progress.values() if item.get("bookmark"))
    notes = sum(1 for item in progress.values() if item.get("notes"))
    active_days = len(user_doc.get("external_daily_counts") or {})
    for item in progress.values():
        timestamp = item.get("timestamp")
        if timestamp and item.get("done"):
            active_days += 0  # only keeping route-compatible summary fields

    total_solved = len(solved_items) + sum(max(value, 0) for key, value in external_totals.items() if key in {"LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder"})

    return {
        "metadata": [
            ("Name", user_doc.get("name") or "-"),
            ("Email", user_doc.get("email") or "-"),
            ("College", user_doc.get("college") or "-"),
            ("Role", "Admin" if user_doc.get("is_admin") else "User"),
            ("Created", _format_datetime(user_doc.get("created_at"))),
            ("Last Sync", _format_datetime(user_doc.get("last_sync"))),
        ],
        "summary": {
            "solved_in_app": len(solved_items),
            "bookmarks": bookmarks,
            "notes": notes,
            "total_solved": total_solved,
            "active_days": active_days,
        },
        "platform_accounts": platform_accounts,
        "recent_activity": recent_activity[:8],
    }


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


@admin_bp.route("/users/<user_id>", methods=["GET"])
@login_required
@admin_required
def user_detail(user_id):
    search_term = request.args.get("q", "").strip()
    page = max(_safe_int(request.args.get("page", 1), 1), 1)

    if not ObjectId.is_valid(user_id):
        flash("Invalid user id.", "danger")
        return redirect(url_for("admin.dashboard", q=search_term, page=page))

    target_id = ObjectId(user_id)
    user_doc = db.user.find_one(
        {"_id": target_id},
        {
            "name": 1,
            "email": 1,
            "college": 1,
            "is_admin": 1,
            "created_at": 1,
            "last_sync": 1,
            "progress": 1,
            "external_totals": 1,
            "external_daily_counts": 1,
            "leetcode_username": 1,
            "github_username": 1,
            "gfg_username": 1,
            "codingninjas_username": 1,
            "hackerrank_username": 1,
            "atcoder_username": 1,
        },
    )
    if not user_doc:
        flash("User not found.", "danger")
        return redirect(url_for("admin.dashboard", q=search_term, page=page))

    detail = _build_admin_user_detail(user_doc)
    return render_template(
        "admin/user_detail.html",
        user_doc=user_doc,
        detail=detail,
        search_term=search_term,
        page=page,
    )


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
