import math
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask import session
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import cache, db
from app.leaderboard.cache import invalidate_leaderboard_cache
from app.profile.sync_service import clear_profile_caches
from app.utils import get_merged_daily_counts


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

    total_submissions = 0
    active_users_today = set()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    projection = {"progress": 1, "external_totals": 1, "external_daily_counts": 1, "platform_calendars": 1}
    for user in db.user.find({}, projection):
        progress = user.get("progress") or {}
        solved_in_app = 0

        for progress_item in progress.values():
            if progress_item.get("done"):
                solved_in_app += 1
                solved_at = progress_item.get("timestamp")
                if (
                    solved_at
                    and hasattr(solved_at, "strftime")
                    and solved_at.strftime("%Y-%m-%d") == today
                ):
                    active_users_today.add(user["_id"])

        external_totals = user.get("external_totals") or {}
        external_solved = sum(
            max(external_totals.get(key, 0), 0)
            for key in ("LeetCode", "GFG", "Coding Ninjas", "HackerRank")
        )

        daily_counts = get_merged_daily_counts(user)
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


@admin_bp.route("/challenges", methods=["GET"])
@login_required
@admin_required
def challenges():
    challenges_list = list(db.challenge.find().sort("week_num", 1))
    return render_template("admin/challenges.html", challenges=challenges_list)


@admin_bp.route("/challenges/new", methods=["GET", "POST"])
@admin_bp.route("/challenges/<challenge_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_challenge(challenge_id=None):
    challenge_doc = None
    if challenge_id:
        try:
            challenge_doc = db.challenge.find_one({"_id": ObjectId(challenge_id)})
        except InvalidId:
            abort(404)
        if not challenge_doc:
            abort(404)

    if request.method == "POST":
        form_token = request.form.get("csrf_token", "")
        session_token = session.get("csrf_token", "")
        if not form_token or not session_token or form_token != session_token:
            abort(400)

        week_num = request.form.get("week_num")
        title = request.form.get("title")
        start_date_raw = request.form.get("start_date")
        end_date_raw = request.form.get("end_date")
        selected_qids = request.form.getlist("question_ids")

        if not week_num or not title:
            flash("Week Number and Title are required.", "danger")
            return redirect(request.referrer or url_for("admin.challenges"))

        try:
            week_num = int(week_num)
        except ValueError:
            flash("Week Number must be an integer.", "danger")
            return redirect(request.referrer or url_for("admin.challenges"))

        start_date = None
        end_date = None
        if start_date_raw:
            try:
                start_date = datetime.fromisoformat(start_date_raw).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass
        if end_date_raw:
            try:
                end_date = datetime.fromisoformat(end_date_raw).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass

        q_ids = []
        for qid in selected_qids:
            try:
                q_ids.append(ObjectId(qid))
            except InvalidId:
                pass

        update_data = {
            "week_num": week_num,
            "title": title,
            "question_ids": q_ids,
            "start_date": start_date,
            "end_date": end_date,
        }

        query = {"week_num": week_num}
        if challenge_doc:
            query["_id"] = {"$ne": challenge_doc["_id"]}
        if db.challenge.find_one(query):
            flash(f"A challenge for Week {week_num} already exists.", "danger")
            return redirect(request.referrer or url_for("admin.challenges"))

        if challenge_doc:
            db.challenge.update_one(
                {"_id": challenge_doc["_id"]}, {"$set": update_data}
            )
            flash(f"Challenge '{title}' updated successfully.", "success")
        else:
            db.challenge.insert_one(update_data)
            flash(f"Challenge '{title}' created successfully.", "success")

        return redirect(url_for("admin.challenges"))

    topics = list(db.topic.find().sort("position", 1))
    questions = list(db.question.find({}, {"problem": 1, "topic": 1}))

    questions_by_topic = {}
    for q in questions:
        questions_by_topic.setdefault(str(q["topic"]), []).append(q)

    selected_qid_strs = set()
    if challenge_doc:
        selected_qid_strs = {str(qid) for qid in challenge_doc.get("question_ids", [])}

    return render_template(
        "admin/edit_challenge.html",
        challenge=challenge_doc,
        topics=topics,
        questions_by_topic=questions_by_topic,
        selected_qids=selected_qid_strs,
    )


@admin_bp.route("/challenges/<challenge_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_challenge(challenge_id):
    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        abort(400)

    try:
        challenge_id_obj = ObjectId(challenge_id)
    except InvalidId:
        abort(404)

    result = db.challenge.delete_one({"_id": challenge_id_obj})
    if result.deleted_count != 1:
        abort(500)

    flash("Challenge deleted successfully.", "success")
    return redirect(url_for("admin.challenges"))
