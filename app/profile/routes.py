import base64
import json
import os
import time

# Comment out cloudinary for now if not installed
# import cloudinary
# import cloudinary.uploader
# import cloudinary.api
import requests
from flask import Blueprint, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from flask import Response
import time
from card_generator import generate_progress_card

from app.extensions import db
from app.extensions import limiter, cache
from app.platforms.fetchers import (
    fetch_coding_ninjas,
    fetch_gfg,
    fetch_github,
    fetch_hr_badges,
    fetch_lc_badges,
    fetch_leetcode,
    fetch_leetcode_rating_history,
)
from app.utils import ensure_utc_datetime, normalize_coding_ninjas_profile_id, utc_now
from profile_validation import build_profile_updates
from progress_export import build_progress_csv

# THIS LINE IS IMPORTANT - defines the blueprint
profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/sync_platforms", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def sync_platforms():
    data = request.json
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

    combined = {}
    totals = {}
    if lc_user:
        lc = fetch_leetcode(lc_user)
        for key, value in lc.get("calendar", {}).items():
            combined[key] = combined.get(key, 0) + value
        if lc.get("total"):
            totals["LeetCode"] = lc.get("total")
        if lc.get("difficulty"):
            totals["LeetCode_Easy"] = lc["difficulty"].get("Easy", 0)
            totals["LeetCode_Medium"] = lc["difficulty"].get("Medium", 0)
            totals["LeetCode_Hard"] = lc["difficulty"].get("Hard", 0)
        if lc.get("contest"):
            totals["LeetCode_Contests"] = lc["contest"].get("attendedContestsCount", 0)
            totals["LeetCode_Rating"] = int(lc["contest"].get("rating", 0))
            totals["LeetCode_GlobalRank"] = lc["contest"].get("globalRanking", 0)

        rating_history = fetch_leetcode_rating_history(lc_user)
        if rating_history:
            update_fields["rating_history"] = rating_history

        lc_badges = fetch_lc_badges(lc_user)
        update_fields["lc_badges_json"] = json.dumps(lc_badges)

    if gh_user:
        gh = fetch_github(gh_user)
        for key, value in gh.get("calendar", {}).items():
            combined[key] = combined.get(key, 0) + value
        if gh.get("stats"):
            totals["GitHub_Issues"] = gh["stats"]["issues"]
            totals["GitHub_PRs"] = gh["stats"]["prs"]
            totals["GitHub_Merged_PRs"] = gh["stats"]["merged_prs"]
            totals["GitHub_Commits"] = gh["stats"]["commits"]

    if gfg_user:
        gfg = fetch_gfg(gfg_user)
        if gfg.get("total"):
            totals["GFG"] = int(gfg.get("total", 0))

    if cn_user:
        cn = fetch_coding_ninjas(cn_user)
        if cn.get("total"):
            totals["Coding Ninjas"] = int(cn.get("total", 0))

    if hr_user:
        try:
            hr_badges, hr_solved = fetch_hr_badges(hr_user)
            update_fields["hr_badges_json"] = json.dumps(hr_badges)
            if hr_solved > 0:
                totals["HackerRank"] = hr_solved
        except Exception:
            print("Unable to fetch HackerRank badges")

    update_fields["external_daily_counts"] = combined
    update_fields["external_totals"] = totals
    db.user.update_one({"_id": user_id}, {"$set": update_fields})
    current_user.reload()

    cache.clear()
    
    return jsonify({"success": True})


@profile_bp.route("/edit_profile", methods=["POST"])
@login_required
def edit_profile():
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
        c_score = user.get("c_score", 0)
        dsa_progress = user.get("dsa_progress", 0)
        current_streak = user.get("current_streak", 0)
        platforms = user.get("platforms", {})        
        img_io = generate_progress_card(name, c_score, dsa_progress, current_streak, platforms)
        img_io.seek(0)
        
        card_cache[user_id] = (current_time, img_io)
        return send_file(img_io, mimetype="image/png")
    except Exception as e:
        return str(e), 500


@profile_bp.route("/search_universities")
def search_universities():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        response = requests.get(f"http://universities.hipolabs.com/search?name={query}", timeout=5)
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
    return jsonify({"success": False, "error": "Photo upload disabled (Cloudinary not configured)"}), 500


@profile_bp.route("/profile")
@login_required
def profile():
    topics = list(db.topic.find().sort("position", 1))
    user = current_user

    all_questions = list(db.question.find())
    solved_items = {question_id: progress for question_id, progress in user.progress.items() if progress.get("done")}

    # ===== Count difficulties from DSA questions =====
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
    # ================================================

    platforms = {"LeetCode": 0, "GFG": 0, "Coding Ninjas": 0, "HackerRank": 0, "Other": 0}
    daily_counts = {}

    topic_question_count = {}
    for question in all_questions:
        topic_id = str(question["topic"])
        topic_question_count.setdefault(topic_id, []).append(str(question["_id"]))

        question_id = str(question["_id"])
        if question_id in solved_items:
            url = (question.get("url") or "").lower()
            if "leetcode.com" in url:
                platforms["LeetCode"] += 1
            elif "geeksforgeeks.org" in url:
                platforms["GFG"] += 1
            elif "codingninjas.com" in url:
                platforms["Coding Ninjas"] += 1
            elif "hackerrank.com" in url:
                platforms["HackerRank"] += 1
            else:
                platforms["Other"] += 1

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
    platforms["LeetCode"] = max(platforms["LeetCode"], ext_totals.get("LeetCode", 0))
    platforms["GFG"] = max(platforms["GFG"], ext_totals.get("GFG", 0))
    platforms["Coding Ninjas"] = max(platforms["Coding Ninjas"], ext_totals.get("Coding Ninjas", 0))
    platforms["HackerRank"] = max(platforms["HackerRank"], ext_totals.get("HackerRank", 0))

    # Use DSA difficulties for the chart
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


@profile_bp.route('/export_csv', endpoint='export_csv')
@login_required
def export_csv():
    # Build CSV of all questions + user's progress and return as attachment
    try:
        all_questions = list(db.question.find())
        topic_lookup = {t['_id']: t.get('name', '') for t in db.topic.find()}
        csv_text = build_progress_csv(all_questions, topic_lookup, current_user.progress or {})
        return Response(
            csv_text,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=progress.csv'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
