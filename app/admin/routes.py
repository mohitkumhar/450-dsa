import math
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask import session
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import cache, db
from app.leaderboard.cache import invalidate_leaderboard_cache
from app.profile.sync_service import clear_profile_caches



admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tail_file(file_path, max_lines=80):
    with file_path.open("r", encoding="utf-8", errors="replace") as file_obj:
        return list(deque(file_obj, maxlen=max_lines))


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
    has_more = False
    per_file_limit = max(10, max_entries // max(1, len(existing)))
    for file_path in existing:
        try:
            lines = _tail_file(file_path, max_lines=per_file_limit)
        except OSError:
            continue
        if len(lines) >= per_file_limit:
            has_more = True
        rel_path = file_path.relative_to(root_dir).as_posix()
        for line in lines:
            text = line.rstrip("\n")
            if not text:
                continue
            entries.append({"source": rel_path, "line": text})
            if len(entries) >= max_entries:
                return entries, True

    return entries, has_more


def _compute_system_stats():
    total_users = db.user.count_documents({})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total_submissions = 0
    active_users_today = 0

    pipeline = [
        {"$match": {"is_deactivated": {"$ne": True}}},
        {"$project": {
            "progress_array": {"$objectToArray": {"$ifNull": ["$progress", {}]}},
            "ext_totals": {"$ifNull": ["$external_totals", {}]},
            "ext_daily": {"$ifNull": ["$external_daily_counts", {}]},
            "platform_calendars": 1,
        }},
    ]

    for user in db.user.aggregate(pipeline):
        solved_count = 0
        user_active = False
        for p in user.get("progress_array", []):
            if p.get("v", {}).get("done"):
                solved_count += 1
                ts = p["v"].get("timestamp")
                if ts and hasattr(ts, "strftime") and ts.strftime("%Y-%m-%d") == today:
                    user_active = True

        ext = user.get("ext_totals", {})
        ext_solved = sum(
            max(ext.get(k, 0), 0)
            for k in ("LeetCode", "GFG", "Coding Ninjas", "HackerRank")
        )

        if not user_active:
            ext_daily = user.get("ext_daily", {})
            if ext_daily.get(today, 0) > 0:
                user_active = True

        if not user_active:
            calendars = user.get("platform_calendars", {})
            if isinstance(calendars, dict):
                for cal in calendars.values():
                    if isinstance(cal, dict) and cal.get(today, 0) > 0:
                        user_active = True
                        break

        total_submissions += solved_count + ext_solved
        if user_active:
            active_users_today += 1

    return {
        "total_users": total_users,
        "total_submissions": total_submissions,
        "active_users_today": active_users_today,
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
    return render_template(
        "admin/dashboard.html",
        users=users,
        search_term=search_term,
        page=page,
        per_page=per_page,
        total_matching=total_matching,
        total_pages=total_pages,
        stats=stats,
    )


@admin_bp.route("/logs", methods=["GET"])
@login_required
@admin_required
def recent_logs():
    log_page = max(_safe_int(request.args.get("page", 1), 1), 1)
    log_page_size = 25
    max_log_entries = min(log_page * log_page_size, 200)
    recent_logs_result = _recent_error_logs(max_entries=max_log_entries)
    if isinstance(recent_logs_result, tuple):
        logs, has_more_logs = recent_logs_result
    else:
        logs, has_more_logs = recent_logs_result, False
    return jsonify(
        {
            "logs": logs,
            "has_more": has_more_logs,
            "page": log_page,
            "page_size": log_page_size,
        }
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

    invalidate_leaderboard_cache()
    clear_profile_caches(cache, target_id)

    display_name = target_user.get("name") or target_user.get("email") or "user"
    flash(f"Deleted account for {display_name}.", "success")
    return redirect(url_for("admin.dashboard", q=search_term, page=page))
