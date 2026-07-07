import math
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask import session, current_app
from flask_login import current_user, login_required

from app.admin.sheet_scraper import scrape_codolio_sheet, validate_codolio_url, ZERO_STATS
from app.decorators import admin_required
from app.extensions import cache, db
from app.leaderboard.cache import invalidate_leaderboard_cache
from app.profile.sync_service import clear_profile_caches

from .import_service import apply_import, parse_import_data, preview_import, validate_import_data



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


@admin_bp.route("/import", methods=["GET", "POST"])
@login_required
@admin_required
def import_sheet():
    if request.method == "GET":
        return render_template("admin/import.html")

    confirm = request.form.get("confirm") == "yes"

    if confirm:
        raw_content = request.form.get("raw_content", "")
        filename = request.form.get("file", "import.json")
        if not raw_content:
            flash("Session expired. Please re-upload the file.", "danger")
            return render_template("admin/import.html")
        try:
            parsed = parse_import_data(raw_content, filename)
        except (ValueError, json.JSONDecodeError) as exc:
            flash(f"Parse error: {exc}", "danger")
            return render_template("admin/import.html")
    else:
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Please select a file to upload.", "danger")
            return render_template("admin/import.html")
        filename = file.filename
        try:
            content = file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            flash("File must be UTF-8 encoded.", "danger")
            return render_template("admin/import.html")
        try:
            parsed = parse_import_data(content, filename)
        except (ValueError, json.JSONDecodeError) as exc:
            flash(f"Parse error: {exc}", "danger")
            return render_template("admin/import.html")

    validation_errors = validate_import_data(parsed)
    if validation_errors:
        for err in validation_errors:
            flash(err, "danger")
        return render_template("admin/import.html")

    if confirm:
        apply_import(parsed)
        total_q = sum(len(t.get("questions", [])) for t in parsed)
        total_t = len(parsed)
        flash(f"Imported {total_t} topics with {total_q} questions.", "success")
        return redirect(url_for("admin.dashboard"))

    preview = preview_import(parsed)
    return render_template(
        "admin/import.html",
        preview=preview,
        filename=filename,
        raw_content=content,
        topics=parsed,
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


# ---------------------------------------------------------------------------
# Sheet Import
# ---------------------------------------------------------------------------

def _next_question_id() -> int:
    """Return the next sequential questionId (max existing + 1)."""
    result = db.question.find_one(
        {"questionId": {"$exists": True, "$type": "number"}},
        {"questionId": 1},
        sort=[("questionId", -1)],
    )
    return (result["questionId"] + 1) if result else 1


def _slug(text: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9-]", "-", text.lower().strip()).strip("-")


def _save_imported_sheet(result: dict) -> dict:
    """
    Persist scraped sheet + questions to MongoDB.
    Returns {inserted, updated, skipped, sheet_id, sheet_url}
    """
    now = datetime.now(timezone.utc)
    sheet_name = result["sheet_name"].strip()
    sheet_slug = result["sheet_slug"].strip()
    questions = result["questions"]

    # 1. Upsert the sheet document
    sheet_doc = {
        "name":           sheet_name,
        "sheetId":        sheet_slug,
        "author":         "Imported",
        "description":    result.get("description", ""),
        "totalQuestions": len(questions),
        "tags":           ["DSA", "Imported"],
        "updatedAt":      now,
    }
    db.sheet.update_one(
        {"sheetId": sheet_slug},
        {"$set": sheet_doc, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )

    # 2. Upsert each question
    inserted = updated = skipped = 0
    next_id = _next_question_id()

    for q in questions:
        title = q.get("title", "").strip()
        if not title:
            skipped += 1
            continue

        title_slug = _slug(title)
        url = q.get("url", "").strip()
        difficulty = q.get("difficulty", "Medium")
        topics = q.get("topics") or []
        companies = q.get("companies") or []
        url2 = q.get("url2", "").strip()

        # Check if question already exists by title (case-insensitive)
        existing = db.question.find_one(
            {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}},
            {"_id": 1, "questionId": 1, "companies": 1, "topics": 1, "sheetIds": 1},
        )

        if existing:
            # Merge companies & topics; keep existing richer data.
            # STATS POLICY: never touch stats for existing questions —
            # they reflect real in-app interactions and must not be reset.
            merge_companies = list(set(existing.get("companies", []) + companies))
            merge_topics    = list(set(existing.get("topics", []) + topics))
            merge_sheet_ids = list(set(existing.get("sheetIds", []) + [sheet_slug]))
            db.question.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "companies": merge_companies,
                    "topics":    merge_topics,
                    "sheetIds":  merge_sheet_ids,
                    "updatedAt": now,
                }},
            )
            updated += 1
        else:
            # Insert new question.
            # STATS POLICY: always use ZERO_STATS — never import stats
            # from external sources. Stats grow from app interactions only.
            q_id = next_id
            next_id += 1
            db.question.insert_one({
                "questionId":      q_id,
                "titleSlug":       title_slug,
                "title":           title,
                "content":         "",
                "difficulty":      difficulty,
                "topics":          topics,
                "companies":       companies,
                "sheetIds":        [sheet_slug],
                "examples":        [],
                "constraints":     [],
                "similarQuestions":[],
                "stats":           dict(ZERO_STATS),   # always zero — never from Codolio
                "status":          "published",
                "createdAt":       now,
                "updatedAt":       now,
                # Legacy fields
                "problem":         title,
                "url":             url,
                "url2":            url2,
                "hints":           [],
                "editorial_links": [],
            })
            inserted += 1

    return {
        "inserted": inserted,
        "updated":  updated,
        "skipped":  skipped,
        "sheet_url": url_for("sheet.sheet_view", sheet_id=sheet_slug, _external=False),
    }


@admin_bp.route("/sheets/import", methods=["GET"])
@login_required
@admin_required
def import_sheet():
    return render_template("admin/import_sheet.html")


@admin_bp.route("/sheets/import/preview", methods=["POST"])
@login_required
@admin_required
def import_sheet_preview():
    """AJAX: scrape the URL and return a JSON preview before saving."""
    url = (request.json or {}).get("url", "").strip()
    ok, err = validate_codolio_url(url)
    if not ok:
        return jsonify({"error": err}), 400

    result = scrape_codolio_sheet(url)
    if result.get("error"):
        return jsonify({"error": result["error"]}), 422

    # Return preview — only first 10 questions to keep payload small
    preview = {
        "sheet_name":  result["sheet_name"],
        "sheet_slug":  result["sheet_slug"],
        "description": result["description"],
        "total":       result["total"],
        "source":      result["source"],
        "sample":      result["questions"][:10],
        # Store full result in session for the save step
    }
    # Stash in session (will be used by save endpoint)
    session["_import_result"] = result
    return jsonify(preview)


@admin_bp.route("/sheets/import/save", methods=["POST"])
@login_required
@admin_required
def import_sheet_save():
    """AJAX: persist the previously scraped result from session."""
    result = session.pop("_import_result", None)
    if not result:
        return jsonify({"error": "No pending import. Please preview first."}), 400
    if result.get("error"):
        return jsonify({"error": result["error"]}), 422
    try:
        stats = _save_imported_sheet(result)
        return jsonify({"ok": True, **stats})
    except Exception as exc:
        current_app.logger.error(f"Sheet import save failed: {exc}")
        return jsonify({"error": f"Database error: {exc}"}), 500

