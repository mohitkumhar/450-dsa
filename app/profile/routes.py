import json

import requests
from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.extensions import cache, db, limiter
from app.leaderboard.cache import invalidate_leaderboard_cache
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
from app.profile.card_service import CACHE_TTL, get_public_card_image
from app.utils import ensure_utc_datetime, json_error, json_success, normalize_coding_ninjas_profile_id, utc_now, compute_user_platforms
from platform_fetcher import run_fetch_jobs
from profile_validation import build_profile_updates

profile_bp = Blueprint("profile", __name__)

__all__ = ["CACHE_TTL", "get_public_card_image"]


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


def clear_profile_caches(user_id):
    try:
        cache.delete(f"card_{str(user_id)}")
    except KeyError:
        pass


def build_platform_sync_jobs(
    leetcode_username="",
    github_username="",
    gfg_username="",
    codingninjas_username="",
    hackerrank_username="",
    atcoder_username="",
):
    jobs = {}

    if leetcode_username:
        def fetch_leetcode_bundle():
            result = {"stats": fetch_leetcode(leetcode_username)}
            try:
                rating_history = fetch_leetcode_rating_history(leetcode_username)
                if rating_history:
                    result["rating_history"] = rating_history
            except Exception:
                pass
            try:
                result["badges"] = fetch_lc_badges(leetcode_username)
            except Exception:
                pass
            return result

        jobs["leetcode"] = fetch_leetcode_bundle

    if github_username:
        jobs["github"] = lambda: fetch_github(github_username)

    if gfg_username:
        jobs["gfg"] = lambda: fetch_gfg(gfg_username)

    if codingninjas_username:
        jobs["codingninjas"] = lambda: fetch_coding_ninjas(codingninjas_username)

    if hackerrank_username:
        jobs["hackerrank"] = lambda: fetch_hr_badges(hackerrank_username)

    if atcoder_username:
        jobs["atcoder"] = lambda: fetch_atcoder(atcoder_username)

    return jobs


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
            return json_error(f"Please wait {mins}m {secs}s before syncing again.", status_code=200)

    update_fields = {"last_sync": now}

    leetcode_username = current_user.leetcode_username or ""
    github_username = current_user.github_username or ""
    gfg_username = current_user.gfg_username or ""
    hackerrank_username = current_user.hackerrank_username or ""
    codingninjas_username = current_user.codingninjas_username or ""
    atcoder_username = current_user.atcoder_username or ""

    if "leetcode" in data:
        leetcode_username = data.get("leetcode", "").strip()
        update_fields["leetcode_username"] = leetcode_username
    if "github" in data:
        github_username = data.get("github", "").strip()
        update_fields["github_username"] = github_username
    if "gfg" in data:
        gfg_username = data.get("gfg", "").strip()
        update_fields["gfg_username"] = gfg_username
    if "hackerrank" in data:
        hackerrank_username = data.get("hackerrank", "").strip()
        update_fields["hackerrank_username"] = hackerrank_username
    if "codingninjas" in data:
        codingninjas_username = normalize_coding_ninjas_profile_id(data.get("codingninjas", ""))
        update_fields["codingninjas_username"] = codingninjas_username
    if "atcoder" in data:
        atcoder_username = data.get("atcoder", "").strip()
        update_fields["atcoder_username"] = atcoder_username

    combined_daily_counts = {}
    platform_totals = {}
    platform_status = {}

    def _mark(platform_key: str, status: str, error: str = None):
        payload = {"status": status}
        if error:
            payload["error"] = error
        platform_status[platform_key] = payload

    platform_jobs = build_platform_sync_jobs(
        leetcode_username=leetcode_username,
        github_username=github_username,
        gfg_username=gfg_username,
        codingninjas_username=codingninjas_username,
        hackerrank_username=hackerrank_username,
        atcoder_username=atcoder_username,
    )
    platform_results, platform_errors = run_fetch_jobs(platform_jobs, max_workers=4)

    if leetcode_username:
        leetcode_bundle = platform_results.get("leetcode") or {}
        leetcode_data = leetcode_bundle.get("stats") if isinstance(leetcode_bundle, dict) else None
        if platform_errors.get("leetcode"):
            _mark("leetcode", "failed", "Failed to fetch LeetCode stats.")
        elif not leetcode_data:
            _mark("leetcode", "failed", "No data returned (username may be invalid or rate-limited).")
        else:
            _mark("leetcode", "synced")
            for key, value in leetcode_data.get("calendar", {}).items():
                combined_daily_counts[key] = combined_daily_counts.get(key, 0) + value
            if leetcode_data.get("total") is not None:
                platform_totals["LeetCode"] = leetcode_data.get("total")
            if leetcode_data.get("difficulty"):
                platform_totals["LeetCode_Easy"] = leetcode_data["difficulty"].get("Easy", 0)
                platform_totals["LeetCode_Medium"] = leetcode_data["difficulty"].get("Medium", 0)
                platform_totals["LeetCode_Hard"] = leetcode_data["difficulty"].get("Hard", 0)
            if leetcode_data.get("contest"):
                platform_totals["LeetCode_Contests"] = leetcode_data["contest"].get("attendedContestsCount", 0)
                platform_totals["LeetCode_Rating"] = int(leetcode_data["contest"].get("rating", 0))
                platform_totals["LeetCode_GlobalRank"] = leetcode_data["contest"].get("globalRanking", 0)
            if leetcode_bundle.get("rating_history"):
                update_fields["rating_history"] = leetcode_bundle["rating_history"]
            if "badges" in leetcode_bundle:
                update_fields["lc_badges_json"] = json.dumps(leetcode_bundle.get("badges") or [])
    else:
        _mark("leetcode", "skipped")

    if github_username:
        github_data = platform_results.get("github")
        if platform_errors.get("github"):
            _mark("github", "failed", "Failed to fetch GitHub stats.")
        elif not github_data:
            _mark("github", "failed", "No data returned (username may be invalid or rate-limited).")
        elif github_data.get("error"):
            if github_data["error"] == "rate_limited":
                _mark("github", "failed", "GitHub API rate limit reached. Please try again later.")
            else:
                _mark("github", "failed", "GitHub API returned an error. Please try again later.")
        else:
            _mark("github", "synced")
            for key, value in github_data.get("calendar", {}).items():
                combined_daily_counts[key] = combined_daily_counts.get(key, 0) + value
            if github_data.get("stats"):
                platform_totals["GitHub_Issues"] = github_data["stats"]["issues"]
                platform_totals["GitHub_PRs"] = github_data["stats"]["prs"]
                platform_totals["GitHub_Merged_PRs"] = github_data["stats"]["merged_prs"]
                platform_totals["GitHub_Commits"] = github_data["stats"]["commits"]
    else:
        _mark("github", "skipped")

    if gfg_username:
        gfg_data = platform_results.get("gfg")
        if platform_errors.get("gfg"):
            _mark("gfg", "failed", "Failed to fetch GFG stats.")
        elif not gfg_data:
            _mark("gfg", "failed", "No data returned (username may be invalid or rate-limited).")
        else:
            _mark("gfg", "synced")
            if gfg_data.get("total") is not None:
                platform_totals["GFG"] = int(gfg_data.get("total", 0))
    else:
        _mark("gfg", "skipped")

    if codingninjas_username:
        codingninjas_data = platform_results.get("codingninjas")
        if platform_errors.get("codingninjas"):
            _mark("codingninjas", "failed", "Failed to fetch Coding Ninjas stats.")
        elif not codingninjas_data:
            _mark("codingninjas", "failed", "No data returned (username may be invalid or rate-limited).")
        else:
            _mark("codingninjas", "synced")
            if codingninjas_data.get("total") is not None:
                platform_totals["Coding Ninjas"] = int(codingninjas_data.get("total", 0))
    else:
        _mark("codingninjas", "skipped")

    if hackerrank_username:
        hackerrank_data = platform_results.get("hackerrank")
        if platform_errors.get("hackerrank"):
            _mark("hackerrank", "failed", "Failed to fetch HackerRank stats.")
        elif not hackerrank_data:
            _mark("hackerrank", "failed", "No data returned (username may be invalid or rate-limited).")
        else:
            hr_badges, hr_solved = hackerrank_data
            update_fields["hr_badges_json"] = json.dumps(hr_badges)
            if hr_solved > 0:
                platform_totals["HackerRank"] = hr_solved
            _mark("hackerrank", "synced")
    else:
        _mark("hackerrank", "skipped")

    if atcoder_username:
        atcoder_data = platform_results.get("atcoder")
        if platform_errors.get("atcoder"):
            _mark("atcoder", "failed", "Failed to fetch AtCoder stats.")
        elif not atcoder_data:
            _mark("atcoder", "failed", "No data returned (handle may be invalid or rate-limited).")
        else:
            _mark("atcoder", "synced")
            if atcoder_data.get("total") is not None:
                platform_totals["AtCoder"] = int(atcoder_data.get("total", 0))
    else:
        _mark("atcoder", "skipped")

    update_fields["external_daily_counts"] = combined_daily_counts
    update_fields["external_totals"] = platform_totals
    db.user.update_one({"_id": user_id}, {"$set": update_fields})
    current_user.reload()

    invalidate_leaderboard_cache()
    clear_profile_caches(user_id)
    return jsonify(build_sync_platforms_response(platform_status))


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
    data = request.get_json()
    if not data:
        return json_error("No data", status_code=400)
    update_fields, error = build_profile_updates(data)
    if error:
        return json_error(error, status_code=400)
    if update_fields:
        db.user.update_one({"_id": current_user.id}, {"$set": update_fields})
        current_user.reload()
        invalidate_leaderboard_cache()
        clear_profile_caches(current_user.id)
    return json_success()


@profile_bp.route("/u/<user_id>/card.png")
def public_card(user_id):
    from bson.objectid import ObjectId
    try:
        object_id = ObjectId(user_id)
    except Exception:
        return "Invalid User ID", 400

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

    ext_platform_totals = user.external_totals or {}
    platforms = compute_user_platforms(solved_items, ext_platform_totals, all_questions)

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
