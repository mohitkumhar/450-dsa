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


admin_bp = Blueprint("admin", __name__, template_folder="templates")

def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@login_required
@admin_required
def dashboard():
    """Admin control panel interface metric layout render."""
    return render_template("admin/dashboard.html")

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

    log_admin_action(
        action_type="DELETE_USER",
        target_entity="USER",
        target_id=user_id,
        result="SUCCESS"
    )

    db.users.delete_one({"_id": ObjectId(user_id)})
    if 'clear_profile_caches' in globals():
        clear_profile_caches(user_id)
    
    flash("User deleted successfully.", "success")
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

