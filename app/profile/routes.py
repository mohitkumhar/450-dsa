import json
from datetime import timedelta

import requests
from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.extensions import cache, db, limiter
from app.leaderboard.cache import invalidate_leaderboard_cache
from app.leaderboard.service import build_leaderboard_data, get_user_rank_by_c_score
from app.profile.card_service import CACHE_TTL, get_public_card_image, warm_public_card_cache
from app.profile.certificate_service import generate_milestone_certificate
from app.profile.sync_service import (
    build_sync_platforms_response,
    clear_profile_caches,
    sync_user_platforms,
)
from app.utils import (
    compute_in_sheet_platform_counts,
    get_merged_daily_counts,
    json_error,
    json_success,
    merge_platform_counts,
    normalize_timestamp,
    update_computed_stats,
    utc_now,
)
from profile_validation import build_profile_updates
from streaks import compute_streak

profile_bp = Blueprint("profile", __name__)

__all__ = ["CACHE_TTL", "build_sync_platforms_response", "get_public_card_image", "warm_public_card_cache"]

UNIVERSITY_SEARCH_TIMEOUT_SECONDS = 5
HEATMAP_DAYS = 168

MILESTONE_DEFS = {
  "100-solved": {"label": "100 Problems Solved", "threshold": 100},
  "250-solved": {"label": "250 Problems Solved", "threshold": 250},
  "sheet-completed": {"label": "450 DSA Sheet Completed", "threshold": "all"},
}


def filter_heatmap_counts(daily_counts, today=None, days=HEATMAP_DAYS):
    """Return only the daily counts rendered by the profile heatmap."""
    today = today or utc_now().date()
    start = today - timedelta(days=days - 1)
    start_key = start.isoformat()
    today_key = today.isoformat()
    return {
        day: count
        for day, count in daily_counts.items()
        if start_key <= day <= today_key
    }


@profile_bp.route("/sync_platforms", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def sync_platforms():
    """Sync linked coding platform statistics for the authenticated user.
    ---
    tags:
      - Profile
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            leetcode:
              type: string
              description: LeetCode username.
            github:
              type: string
              description: GitHub username.
            gfg:
              type: string
              description: GeeksforGeeks username.
            hackerrank:
              type: string
              description: HackerRank username.
            codingninjas:
              type: string
              description: Coding Ninjas profile id or URL.
    security:
      - SessionAuth: []
    responses:
      200:
        description: Platform sync result.
        schema:
          type: object
          properties:
            success:
              type: boolean
            partial_success:
              type: boolean
            error:
              type: string
            platforms:
              type: object
              additionalProperties:
                type: object
                properties:
                  status:
                    type: string
                    enum:
                      - synced
                      - failed
                      - skipped
                  error:
                    type: string
      401:
        description: Login required.
      400:
        description: Request body must be a JSON object.
      429:
        description: Rate limit exceeded.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Request body must be a JSON object.", status_code=400)
    payload, status_code = sync_user_platforms(current_user, data, db, cache)
    if payload.get("success"):
        warm_public_card_cache(current_user.id, db_handle=db)
    return jsonify(payload), status_code


@profile_bp.route("/edit_profile", methods=["POST"])
@login_required
def edit_profile():
    """Update editable profile fields for the authenticated user.
    ---
    tags:
      - Profile
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              maxLength: 100
            bio:
              type: string
              maxLength: 500
            location:
              type: string
              maxLength: 100
            college:
              type: string
              maxLength: 200
            headline:
              type: string
              maxLength: 150
            linkedin_url:
              type: string
              maxLength: 300
            twitter_url:
              type: string
              maxLength: 300
            website_url:
              type: string
              maxLength: 300
            resume_url:
              type: string
              maxLength: 300
    security:
      - SessionAuth: []
    responses:
      200:
        description: Profile updated successfully.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
      400:
        description: Invalid profile payload.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
      401:
        description: Login required.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be a JSON object."}), 400
    update_fields, error = build_profile_updates(data)
    if error:
        return json_error(error, status_code=400)
    if update_fields:
        db.user.update_one({"_id": current_user.id}, {"$set": update_fields})
        current_user.reload()
        invalidate_leaderboard_cache()
        clear_profile_caches(cache, current_user.id)
        warm_public_card_cache(current_user.id, db_handle=db)
    return json_success()


@profile_bp.route("/u/<user_id>/card.png")
def public_card(user_id):
    from bson.objectid import ObjectId
    try:
        object_id = ObjectId(user_id)
    except Exception:
        return "Invalid User ID", 400

    try:
        user_doc = db.user.find_one({"_id": object_id}, {"is_deactivated": 1})
    except TypeError:
        # Some lightweight test doubles implement a simpler find_one(query) API.
        user_doc = db.user.find_one({"_id": object_id})
    if not user_doc or user_doc.get("is_deactivated"):
        return "User not found", 404

    try:
        img_io, etag, last_modified = get_public_card_image(user_id, object_id, db_handle=db)
    except LookupError:
        return "User not found", 404
    except Exception:
        current_app.logger.exception("Failed to generate public progress card")
        return "Unable to generate progress card", 500
    try:
        img_io.seek(0)
        response = send_file(img_io, mimetype="image/png")
        response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL}"
        response.set_etag(etag)
        if last_modified is not None:
            response.last_modified = last_modified
        response.make_conditional(request)
        return response
    except Exception:
        current_app.logger.exception("Failed to generate public progress card")
        return "Unable to generate progress card", 500


@profile_bp.route("/certificate/<milestone_id>")
@login_required
def milestone_certificate(milestone_id):
    milestone = MILESTONE_DEFS.get(milestone_id)
    if not milestone:
        return "Milestone not found", 404

    progress_data = current_user.progress or {}
    dsa_done = sum(1 for progress_item in progress_data.values() if progress_item.get("done"))
    total_questions = db.question.count_documents({})

    threshold = milestone["threshold"]
    if threshold == "all":
        eligible = total_questions > 0 and dsa_done >= total_questions
    else:
        eligible = dsa_done >= int(threshold)

    if not eligible:
        return "Milestone not reached", 403

    awarded_on = utc_now().date().isoformat()
    img_io = generate_milestone_certificate(current_user.name, milestone["label"], awarded_on=awarded_on)
    filename = f"certificate-{milestone_id}.png"
    return send_file(img_io, mimetype="image/png", as_attachment=True, download_name=filename)


@profile_bp.route("/search_universities")
def search_universities():
    """Return matching universities for an autocomplete query.
    ---
    tags:
      - Profile
    parameters:
      - name: q
        in: query
        type: string
        required: true
        minLength: 2
        description: University name search text.
    responses:
      200:
        description: Matching universities.
        schema:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
              country:
                type: string
              label:
                type: string
    """
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        response = requests.get(
            "https://universities.hipolabs.com/search",
            params={"name": query},
            timeout=UNIVERSITY_SEARCH_TIMEOUT_SECONDS,
        )
        if response.status_code == 200:
            data = response.json()
            seen = set()
            results = []
            for university in data[:30]:
                name = university.get("name", "")
                country = university.get("country", "")
                label = f"{name}, {country}" if country else name
                if label not in seen:
                    seen.add(label)
                    results.append({"name": name, "country": country, "label": label})
            return jsonify(results)
        return jsonify([])
    except Exception:
        return jsonify([])


@profile_bp.route("/upload_photo", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def upload_photo():
    """Upload and save a profile photo for the authenticated user.
    ---
    tags:
      - Profile
    consumes:
      - multipart/form-data
    parameters:
      - name: photo
        in: formData
        type: file
        required: true
        description: Profile image file.
    security:
      - SessionAuth: []
    responses:
      200:
        description: Photo uploaded successfully when an uploader is configured.
        schema:
          type: object
          properties:
            success:
              type: boolean
            photo_url:
              type: string
      401:
        description: Login required.
      429:
        description: Rate limit exceeded.
      500:
        description: Photo upload is currently disabled or upload failed.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
              example: Photo upload disabled (Cloudinary not configured)
    """
    return json_error("Photo upload disabled (Cloudinary not configured)", status_code=500)


@profile_bp.route("/profile")
@login_required
def profile():
    user = current_user
    solved_items = {question_id: progress for question_id, progress in user.progress.items() if progress.get("done")}
    dsa_done = len(solved_items)
    merged_daily_counts = get_merged_daily_counts(user)
    current_streak, longest_streak = compute_streak(user.progress, external_daily_counts=merged_daily_counts)

    pre = current_app.config.get("_PRECOMPUTED")
    if pre:
        topics = pre["topics"]
        all_questions = pre["all_questions"]
        difficulty_map = pre["difficulty_map"]
        topic_question_count = pre["topic_question_count"]
        total_questions = pre["total_questions"]
    else:
        topics = list(db.topic.find().sort("position", 1))
        all_questions = list(db.question.find())
        difficulty_map = {str(q["_id"]): q.get("difficulty", "Medium") for q in all_questions}
        topic_question_count = {}
        for question in all_questions:
            topic_id = str(question["topic"])
            topic_question_count.setdefault(topic_id, []).append(str(question["_id"]))
        total_questions = len(all_questions)

    dsa_easy = 0
    dsa_medium = 0
    dsa_hard = 0

    for q_id in solved_items.keys():
        diff = difficulty_map.get(q_id, "Medium")
        if diff == "Easy":
            dsa_easy += 1
        elif diff == "Medium":
            dsa_medium += 1
        elif diff == "Hard":
            dsa_hard += 1

    platforms = {"LeetCode": 0, "GFG": 0, "Coding Ninjas": 0, "HackerRank": 0, "Other": 0}
    daily_counts = {}

    for question in all_questions:
        question_id = str(question["_id"])
        if question_id in solved_items:
            day = normalize_timestamp(solved_items[question_id].get("timestamp"))
            if day is None:
                continue
            daily_counts[day] = daily_counts.get(day, 0) + 1

    if merged_daily_counts:
        for day, count in merged_daily_counts.items():
            daily_counts[day] = daily_counts.get(day, 0) + count

    total_active_days = len(daily_counts)
    heatmap_daily_counts = filter_heatmap_counts(daily_counts)
    sorted_dates = sorted(daily_counts.keys())
    cumulative_data = []
    cumulative_sum = 0
    for day in sorted_dates:
        cumulative_sum += daily_counts[day]
        cumulative_data.append({"x": day, "y": cumulative_sum})

    topic_progress = []

    ext_platform_totals = user.external_totals or {}
    cached_in_sheet_counts = (
        user.in_sheet_platform_counts
        if isinstance(user.in_sheet_platform_counts, dict)
        else None
    )
    if cached_in_sheet_counts is not None:
        platforms = merge_platform_counts(cached_in_sheet_counts, ext_platform_totals)
    else:
        in_sheet_counts = compute_in_sheet_platform_counts(solved_items, all_questions)

        # Avoid clobbering concurrent $inc updates from /update_question by setting only
        # if the field is still absent at write time.
        update_result = db.user.update_one(
            {"_id": user.id, "in_sheet_platform_counts": {"$exists": False}},
            {"$set": {"in_sheet_platform_counts": in_sheet_counts}},
        )

        effective_counts = in_sheet_counts
        if not getattr(update_result, "modified_count", 0):
            refreshed = db.user.find_one({"_id": user.id}, {"in_sheet_platform_counts": 1}) or {}
            refreshed_counts = refreshed.get("in_sheet_platform_counts")
            if isinstance(refreshed_counts, dict):
                effective_counts = refreshed_counts

        platforms = merge_platform_counts(effective_counts, ext_platform_totals)

    lc_easy = dsa_easy
    lc_medium = dsa_medium
    lc_hard = dsa_hard

    lc_contests = ext_platform_totals.get("LeetCode_Contests", 0)
    lc_rating = ext_platform_totals.get("LeetCode_Rating", 0)
    lc_rank = ext_platform_totals.get("LeetCode_GlobalRank", 0)
    gh_issues = ext_platform_totals.get("GitHub_Issues", 0)
    gh_prs = ext_platform_totals.get("GitHub_PRs", 0)
    gh_merged = ext_platform_totals.get("GitHub_Merged_PRs", 0)
    gh_commits = ext_platform_totals.get("GitHub_Commits", 0)

    global_total_solved = sum(platforms.values())

    for topic_doc in topics:
        topic_id = str(topic_doc["_id"])
        topic_question_ids = topic_question_count.get(topic_id, [])
        topic_done = sum(1 for question_id in topic_question_ids if question_id in solved_items)
        percent = (topic_done / len(topic_question_ids) * 100) if topic_question_ids else 0
        topic_progress.append(
            {
                "name": topic_doc["name"],
                "done": topic_done,
                "total": len(topic_question_ids),
                "percent": round(percent, 1),
            }
        )

    topic_progress.sort(key=lambda item: item["done"], reverse=True)
    overall_percent = round((dsa_done / total_questions * 100) if total_questions > 0 else 0, 1)
    rating_history = list(user.rating_history or [])

    lc_badges = []
    hr_badges = []
    try:
        lc_badges = json.loads(user.lc_badges_json or "[]")
    except json.JSONDecodeError:
        print("Unable to handle leetcode badges")

    try:
        hr_badges = [badge for badge in json.loads(user.hr_badges_json or "[]") if int(badge.get("stars", 0)) > 0]
    except (json.JSONDecodeError, ValueError):
        print("Unable to handle hackerrank badges")

    leaderboard_entries = build_leaderboard_data()
    profile_leaderboard_rank = get_user_rank_by_c_score(user.id, leaderboard_entries)

    update_computed_stats(user.id, user.progress, db, total_questions, user)

    return render_template(
        "profile.html",
        user=user,
        topic_progress=topic_progress,
        dsa_done=dsa_done,
        global_total_solved=global_total_solved,
        total_questions=total_questions,
        overall_percent=overall_percent,
        platforms=platforms,
        lc_easy=lc_easy,
        lc_medium=lc_medium,
        lc_hard=lc_hard,
        lc_contests=lc_contests,
        lc_rating=lc_rating,
        lc_rank=lc_rank,
        gh_issues=gh_issues,
        gh_prs=gh_prs,
        gh_merged=gh_merged,
        gh_commits=gh_commits,
        daily_counts=heatmap_daily_counts,
        cumulative_data=cumulative_data,
        total_active_days=total_active_days,
        rating_history=rating_history,
        lc_badges=lc_badges,
        hr_badges=hr_badges,
        profile_leaderboard_rank=profile_leaderboard_rank,
        current_streak=current_streak,
        longest_streak=longest_streak,
    )
