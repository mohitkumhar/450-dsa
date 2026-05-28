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
from app.extensions import db
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
                if solved_at and hasattr(solved_at, "strftime") and solved_at.strftime("%Y-%m-%d") == today:
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

    display_name = target_user.get("name") or target_user.get("email") or "user"
    flash(f"Deleted account for {display_name}.", "success")
    return redirect(url_for("admin.dashboard", q=search_term, page=page))


import threading
import time
import requests
from flask import current_app

def _background_check_links(app):
    """Background worker to check all unique URLs sequentially and cache results."""
    with app.app_context():
        try:
            # 1. Gather all questions and build list of unique URLs
            all_questions = list(db.question.find())
            url_records = []
            seen_urls = set()
            
            for q in all_questions:
                problem_name = q.get("problem") or "Unknown Question"
                # Primary URL
                u1 = q.get("url", "").strip()
                if u1 and u1.startswith("http") and u1 not in seen_urls:
                    seen_urls.add(u1)
                    url_records.append(u1)
                # Secondary URL
                u2 = q.get("url2", "").strip()
                if u2 and u2.startswith("http") and u2 not in seen_urls:
                    seen_urls.add(u2)
                    url_records.append(u2)
                # Editorial links
                editorials = q.get("editorial_links") or []
                for ed in editorials:
                    if isinstance(ed, dict):
                        u_ed = ed.get("url", "").strip()
                    else:
                        u_ed = str(ed).strip()
                    if u_ed and u_ed.startswith("http") and u_ed not in seen_urls:
                        seen_urls.add(u_ed)
                        url_records.append(u_ed)

            unique_urls = url_records
            total_count = len(unique_urls)
            
            # Update status to running
            db.link_checker_status.update_one(
                {"_id": "status"},
                {
                    "$set": {
                        "is_running": True,
                        "total_links": total_count,
                        "completed_links": 0,
                        "started_at": datetime.now(timezone.utc),
                        "finished_at": None,
                        "summary": "Scan in progress..."
                    }
                },
                upsert=True
            )
            
            completed = 0
            broken_count = 0
            redirect_count = 0
            
            for url in unique_urls:
                # Check cache first (valid for 24 hours)
                cached = db.link_checks.find_one({"_id": url})
                if cached:
                    checked_at = cached.get("checked_at")
                    if checked_at:
                        if checked_at.tzinfo is None:
                            checked_at = checked_at.replace(tzinfo=timezone.utc)
                        elapsed = (datetime.now(timezone.utc) - checked_at).total_seconds()
                        if elapsed < 86400:  # 24 hours
                            completed += 1
                            if cached.get("status") == "broken":
                                broken_count += 1
                            elif cached.get("status") == "redirected":
                                redirect_count += 1
                                
                            db.link_checker_status.update_one(
                                {"_id": "status"},
                                {"$set": {"completed_links": completed}}
                            )
                            continue
                
                # Respect rate limits: sleep 0.2s before request
                time.sleep(0.2)
                
                status_code = -1
                status = "error"
                redirect_url = None
                error_msg = None
                
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                
                try:
                    # Use HEAD first, allow_redirects=False to catch 301/302
                    response = requests.head(url, timeout=5, allow_redirects=False, headers=headers)
                    if response.status_code in (403, 405):
                        response = requests.get(url, timeout=5, allow_redirects=False, headers=headers)
                        
                    status_code = response.status_code
                    if 200 <= status_code < 300:
                        status = "ok"
                    elif 300 <= status_code < 400:
                        status = "redirected"
                        redirect_url = response.headers.get("Location")
                        redirect_count += 1
                    else:
                        status = "broken"
                        broken_count += 1
                except Exception as exc:
                    error_msg = str(exc)
                    broken_count += 1
                    
                # Cache results
                db.link_checks.update_one(
                    {"_id": url},
                    {
                        "$set": {
                            "status_code": status_code,
                            "status": status,
                            "checked_at": datetime.now(timezone.utc),
                            "redirect_url": redirect_url,
                            "error_message": error_msg
                        }
                    },
                    upsert=True
                )
                
                completed += 1
                db.link_checker_status.update_one(
                    {"_id": "status"},
                    {"$set": {"completed_links": completed}}
                )

            # Update final status
            summary = f"Completed. Found {broken_count} broken links and {redirect_count} redirects."
            db.link_checker_status.update_one(
                {"_id": "status"},
                {
                    "$set": {
                        "is_running": False,
                        "completed_links": total_count,
                        "finished_at": datetime.now(timezone.utc),
                        "summary": summary
                    }
                }
            )
        except Exception as thread_exc:
            app.logger.error(f"Error in background link checker thread: {thread_exc}")
            db.link_checker_status.update_one(
                {"_id": "status"},
                {
                    "$set": {
                        "is_running": False,
                        "summary": f"Failed with exception: {thread_exc}"
                    }
                }
            )


@admin_bp.route("/link-checker", methods=["GET"])
@login_required
@admin_required
def link_checker_dashboard():
    # 1. Fetch all questions and extract all configured URLs
    all_questions = list(db.question.find())
    
    unique_urls = set()
    link_items = []
    
    for q in all_questions:
        problem_name = q.get("problem") or "Unknown Question"
        
        # Primary
        u1 = q.get("url", "").strip()
        if u1 and u1.startswith("http"):
            unique_urls.add(u1)
            link_items.append({
                "question_name": problem_name,
                "link_type": "primary",
                "url": u1
            })
            
        # Secondary
        u2 = q.get("url2", "").strip()
        if u2 and u2.startswith("http"):
            unique_urls.add(u2)
            link_items.append({
                "question_name": problem_name,
                "link_type": "secondary",
                "url": u2
            })
            
        # Editorials
        editorials = q.get("editorial_links") or []
        for ed in editorials:
            if isinstance(ed, dict):
                u_ed = ed.get("url", "").strip()
            else:
                u_ed = str(ed).strip()
            if u_ed and u_ed.startswith("http"):
                unique_urls.add(u_ed)
                link_items.append({
                    "question_name": problem_name,
                    "link_type": "editorial",
                    "url": u_ed
                })

    total_links = len(unique_urls)
    
    # 2. Query checked links cache from Mongo
    cache_records = {doc["_id"]: doc for doc in db.link_checks.find()}
    
    # 3. Compile flagged broken or redirected links
    flagged_links = []
    flagged_broken = 0
    flagged_redirects = 0
    cached_count = 0
    
    for item in link_items:
        url = item["url"]
        cache_item = cache_records.get(url)
        if cache_item:
            cached_count += 1
            status = cache_item.get("status", "ok")
            if status in ("broken", "redirected", "error"):
                flagged_links.append({
                    "question_name": item["question_name"],
                    "link_type": item["link_type"],
                    "url": url,
                    "status_code": cache_item.get("status_code", -1),
                    "status": status,
                    "checked_at": cache_item.get("checked_at"),
                    "error_message": cache_item.get("error_message"),
                    "redirect_url": cache_item.get("redirect_url")
                })
                
    for r in cache_records.values():
        if r.get("status") == "broken":
            flagged_broken += 1
        elif r.get("status") == "redirected":
            flagged_redirects += 1
            
    cache_coverage = cached_count / len(link_items) if link_items else 0
    
    # 4. Get active background checker status
    job_status = db.link_checker_status.find_one({"_id": "status"}) or {
        "is_running": False,
        "total_links": 0,
        "completed_links": 0,
        "summary": "No scan run yet."
    }
    
    return render_template(
        "admin/link_checker.html",
        total_links=total_links,
        flagged_broken=flagged_broken,
        flagged_redirects=flagged_redirects,
        cache_coverage=cache_coverage,
        flagged_links=flagged_links,
        job_status=job_status
    )


@admin_bp.route("/link-checker/start", methods=["POST"])
@login_required
@admin_required
def start_link_checker():
    status_doc = db.link_checker_status.find_one({"_id": "status"})
    if status_doc and status_doc.get("is_running"):
        return jsonify({"success": False, "error": "Link Checker scanner is already running."}), 400
        
    flask_app = current_app._get_current_object()
    thread = threading.Thread(target=_background_check_links, args=(flask_app,), daemon=True)
    thread.start()
    
    return jsonify({"success": True})


@admin_bp.route("/link-checker/status", methods=["GET"])
@login_required
@admin_required
def get_link_checker_status():
    status_doc = db.link_checker_status.find_one({"_id": "status"}) or {
        "is_running": False,
        "total_links": 0,
        "completed_links": 0,
        "summary": "No scan run yet."
    }
    finished = status_doc.get("finished_at")
    started = status_doc.get("started_at")
    
    return jsonify({
        "is_running": bool(status_doc.get("is_running")),
        "total_links": status_doc.get("total_links", 0),
        "completed_links": status_doc.get("completed_links", 0),
        "summary": status_doc.get("summary", ""),
        "started_at": started.isoformat() if started else None,
        "finished_at": finished.isoformat() if finished else None
    })


@admin_bp.route("/link-checker/clear", methods=["POST"])
@login_required
@admin_required
def clear_link_checker_cache():
    db.link_checks.delete_many({})
    db.link_checker_status.update_one(
        {"_id": "status"},
        {
            "$set": {
                "is_running": False,
                "completed_links": 0,
                "total_links": 0,
                "finished_at": None,
                "started_at": None,
                "summary": "Checked links cache cleared."
            }
        },
        upsert=True
    )
    return jsonify({"success": True})
