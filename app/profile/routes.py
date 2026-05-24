import json
import os
import time

import requests
from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from card_generator import generate_progress_card

from app.extensions import db
from app.extensions import limiter, cache
from app.platforms.fetchers import (
    fetch_atcoder,
    fetch_coding_ninjas,
    fetch_gfg,
    fetch_github,
    fetch_hr_badges,
    fetch_lc_badges,
    fetch_leetcode,
    fetch_leetcode_rating_history,
)
from app.utils import ensure_utc_datetime, normalize_coding_ninjas_profile_id, utc_now, compute_c_score, compute_user_platforms
from streaks import compute_streak
from profile_validation import build_profile_updates

profile_bp = Blueprint("profile", __name__)


def build_sync_platforms_response(platform_status: dict):
    attempted = sum(1 for value in platform_status.values() if value.get("status") != "skipped")
    synced = sum(1 for value in platform_status.values() if value.get("status") == "synced")
    failed = sum(1 for value in platform_status.values() if value.get("status") == "failed")
    partial_success = bool(synced and failed)

    if attempted == 0:
        return {"success": False, "error": "No platforms provided to sync.", "platforms": platform_status}
    if synced == 0 and failed > 0:
        return {"success": False, "error": "Sync failed for all platforms.", "platforms": platform_status}

    return {"success": True, "partial_success": partial_success, "platforms": platform_status}


@profile_bp.route("/sync_platforms", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def sync_platforms():
    """Sync coding platform statistics for the authenticated user.
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
      429:
        description: Rate limit exceeded.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be a JSON object."}), 400

    now = utc_now()
    user_id = current_user.id

    last_sync = current_user.last_sync
    if last_sync:
        last_sync = ensure_utc_datetime(last_sync)
        diff = (now - last_sync).total_seconds()
        if diff < 600:
            remaining = int(600 - diff)
            mins = remaining // 60
            secs = remaining % 60
            return jsonify({"success": False, "error": f"Please wait {mins}m {secs}s before syncing again."})

    update_fields = {"last_sync": now}

    lc_user = current_user.leetcode_username or ""
    gh_user = current_user.github_username or ""
    gfg_user = current_user.gfg_username or ""
    hr_user = current_user.hackerrank_username or ""
    cn_user = current_user.codingninjas_username or ""
    ac_user = current_user.atcoder_username or ""

    if "leetcode" in data:
        lc_user = data.get("leetcode", "").strip()
        update_fields["leetcode_username"] = lc_user
    if "github" in data:
        gh_user = data.get("github", "").strip()
        update_fields["github_username"] = gh_user
    if "gfg" in data:
        gfg_user = data.get("gfg", "").strip()
        update_fields["gfg_username"] = gfg_user
    if "hackerrank" in data:
        hr_user = data.get("hackerrank", "").strip()
        update_fields["hackerrank_username"] = hr_user
    if "codingninjas" in data:
        cn_user = normalize_coding_ninjas_profile_id(data.get("codingninjas", ""))
        update_fields["codingninjas_username"] = cn_user
    if "atcoder" in data:
        ac_user = data.get("atcoder", "").strip()
        update_fields["atcoder_username"] = ac_user

    combined = {}
    totals = {}
    platform_status = {}

    def _mark(platform_key: str, status: str, error: str = None):
        payload = {"status": status}
        if error:
            payload["error"] = error
        platform_status[platform_key] = payload

    if lc_user:
        try:
            lc = fetch_leetcode(lc_user)
            if not lc:
                _mark("leetcode", "failed", "No data returned (username may be invalid or rate-limited).")
            else:
                _mark("leetcode", "synced")
                for key, value in lc.get("calendar", {}).items():
                    combined[key] = combined.get(key, 0) + value
                if lc.get("total") is not None:
                    totals["LeetCode"] = lc.get("total")
                if lc.get("difficulty"):
                    totals["LeetCode_Easy"] = lc["difficulty"].get("Easy", 0)
                    totals["LeetCode_Medium"] = lc["difficulty"].get("Medium", 0)
                    totals["LeetCode_Hard"] = lc["difficulty"].get("Hard", 0)
                if lc.get("contest"):
                    totals["LeetCode_Contests"] = lc["contest"].get("attendedContestsCount", 0)
                    totals["LeetCode_Rating"] = int(lc["contest"].get("rating", 0))
                    totals["LeetCode_GlobalRank"] = lc["contest"].get("globalRanking", 0)

                try:
                    rating_history = fetch_leetcode_rating_history(lc_user)
                    if rating_history:
                        update_fields["rating_history"] = rating_history
                except Exception:
                    pass

                try:
                    lc_badges = fetch_lc_badges(lc_user)
                    update_fields["lc_badges_json"] = json.dumps(lc_badges)
                except Exception:
                    pass
        except Exception:
            _mark("leetcode", "failed", "Failed to fetch LeetCode stats.")
    else:
        _mark("leetcode", "skipped")

    if gh_user:
        try:
            gh = fetch_github(gh_user)
            if not gh:
                _mark("github", "failed", "No data returned (username may be invalid or rate-limited).")
            else:
                _mark("github", "synced")
                for key, value in gh.get("calendar", {}).items():
                    combined[key] = combined.get(key, 0) + value
                if gh.get("stats"):
                    totals["GitHub_Issues"] = gh["stats"]["issues"]
                    totals["GitHub_PRs"] = gh["stats"]["prs"]
                    totals["GitHub_Merged_PRs"] = gh["stats"]["merged_prs"]
                    totals["GitHub_Commits"] = gh["stats"]["commits"]
        except Exception:
            _mark("github", "failed", "Failed to fetch GitHub stats.")
    else:
        _mark("github", "skipped")

    if gfg_user:
        try:
            gfg = fetch_gfg(gfg_user)
            if not gfg:
                _mark("gfg", "failed", "No data returned (username may be invalid or rate-limited).")
            else:
                _mark("gfg", "synced")
                if gfg.get("total") is not None:
                    totals["GFG"] = int(gfg.get("total", 0))
        except Exception:
            _mark("gfg", "failed", "Failed to fetch GFG stats.")
    else:
        _mark("gfg", "skipped")

    if cn_user:
        try:
            cn = fetch_coding_ninjas(cn_user)
            if not cn:
                _mark("codingninjas", "failed", "No data returned (username may be invalid or rate-limited).")
            else:
                _mark("codingninjas", "synced")
                if cn.get("total") is not None:
                    totals["Coding Ninjas"] = int(cn.get("total", 0))
        except Exception:
            _mark("codingninjas", "failed", "Failed to fetch Coding Ninjas stats.")
    else:
        _mark("codingninjas", "skipped")

    if hr_user:
        try:
            hr_badges, hr_solved = fetch_hr_badges(hr_user)
            update_fields["hr_badges_json"] = json.dumps(hr_badges)
            if hr_solved > 0:
                totals["HackerRank"] = hr_solved
            _mark("hackerrank", "synced")
        except Exception:
            _mark("hackerrank", "failed", "Failed to fetch HackerRank stats.")
    else:
        _mark("hackerrank", "skipped")

    if ac_user:
        try:
            ac = fetch_atcoder(ac_user)
            if not ac:
                _mark("atcoder", "failed", "No data returned (handle may be invalid or rate-limited).")
            else:
                _mark("atcoder", "synced")
                if ac.get("total") is not None:
                    totals["AtCoder"] = int(ac.get("total", 0))
        except Exception:
            _mark("atcoder", "failed", "Failed to fetch AtCoder stats.")
    else:
        _mark("atcoder", "skipped")

    update_fields["external_daily_counts"] = combined
    update_fields["external_totals"] = totals
    db.user.update_one({"_id": user_id}, {"$set": update_fields})
    current_user.reload()

    cache.clear()
    return jsonify(build_sync_platforms_response(platform_status))


@profile_bp.route("/edit_profile", methods=["POST"])
@login_required
def edit_profile():
    """Update profile fields for the authenticated user.
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
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    update_fields, error = build_profile_updates(data)
    if error:
        return jsonify({"success": False, "error": error}), 400
    if update_fields:
        db.user.update_one({"_id": current_user.id}, {"$set": update_fields})
        current_user.reload()
    return jsonify({"success": True})


card_cache = {}
CACHE_TTL = 3600

@profile_bp.route("/u/<user_id>/card.png")
def public_card(user_id):
    from bson.objectid import ObjectId
    try:
        user = db.user.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return "Invalid User ID", 400
        
    if not user:
        return "User not found", 404
        
    current_time = time.time()
    if user_id in card_cache:
        cached_time, cached_image = card_cache[user_id]
        if current_time - cached_time < CACHE_TTL:
            cached_image.seek(0)
            return send_file(cached_image, mimetype="image/png")
            
    try:
        name = user.get("name", "Anonymous")
        
        stats = compute_c_score(user)
        c_score = stats["c_score"]
        dsa_done = stats["dsa_done"]
        
        total_questions = db.question.count_documents({})
        dsa_progress = round((dsa_done / total_questions * 100) if total_questions > 0 else 0, 1)
        
        progress_data = user.get("progress", {})
        current_streak, _ = compute_streak(progress_data)
        
        all_questions = list(db.question.find())
        solved_items = {qid: p for qid, p in progress_data.items() if p.get("done")}
        platforms = compute_user_platforms(solved_items, user.get("external_totals", {}), all_questions)

        from card_generator import generate_progress_card
        img_io = generate_progress_card(name, c_score, dsa_progress, current_streak, platforms)
        
        card_cache[user_id] = (current_time, img_io)
        return send_file(img_io, mimetype="image/png")
    except Exception:
        current_app.logger.exception("Failed to generate public progress card")
        return "Unable to generate progress card", 500


@profile_bp.route("/search_universities")
def search_universities():
    """Search universities by name.
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
            timeout=5,
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
    """Upload a profile photo.
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
    return jsonify({"success": False, "error": "Photo upload disabled (Cloudinary not configured)"}), 500


@profile_bp.route("/profile")
@login_required
def profile():
    topics = list(db.topic.find().sort("position", 1))
    user = current_user

    all_questions = list(db.question.find())
    solved_items = {question_id: progress for question_id, progress in user.progress.items() if progress.get("done")}

    difficulty_map = {str(q["_id"]): q.get("difficulty", "Medium") for q in all_questions}
    
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

    topic_question_count = {}
    for question in all_questions:
        topic_id = str(question["topic"])
        topic_question_count.setdefault(topic_id, []).append(str(question["_id"]))

        question_id = str(question["_id"])
        if question_id in solved_items:
            solved_at = solved_items[question_id].get("timestamp") or utc_now()
            day = solved_at.strftime("%Y-%m-%d")
            daily_counts[day] = daily_counts.get(day, 0) + 1

    ext_daily = user.external_daily_counts
    if ext_daily:
        for day, count in ext_daily.items():
            daily_counts[day] = daily_counts.get(day, 0) + count

    total_active_days = len(daily_counts)
    sorted_dates = sorted(daily_counts.keys())
    cumulative_data = []
    cumulative_sum = 0
    for day in sorted_dates:
        cumulative_sum += daily_counts[day]
        cumulative_data.append({"x": day, "y": cumulative_sum})

    topic_progress = []
    dsa_done = len(solved_items)

    ext_totals = user.external_totals or {}
    platforms = compute_user_platforms(solved_items, ext_totals, all_questions)

    lc_easy = dsa_easy
    lc_medium = dsa_medium
    lc_hard = dsa_hard
    
    lc_contests = ext_totals.get("LeetCode_Contests", 0)
    lc_rating = ext_totals.get("LeetCode_Rating", 0)
    lc_rank = ext_totals.get("LeetCode_GlobalRank", 0)
    gh_issues = ext_totals.get("GitHub_Issues", 0)
    gh_prs = ext_totals.get("GitHub_PRs", 0)
    gh_merged = ext_totals.get("GitHub_Merged_PRs", 0)
    gh_commits = ext_totals.get("GitHub_Commits", 0)

    global_total_solved = sum(platforms.values())
    total_questions = len(all_questions)

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
        daily_counts=daily_counts,
        cumulative_data=cumulative_data,
        total_active_days=total_active_days,
        rating_history=rating_history,
        lc_badges=lc_badges,
        hr_badges=hr_badges,
    )
