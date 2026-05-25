import re
from datetime import datetime, timezone

from flask import jsonify

from app.extensions import db
from app.search import service as search_service


def utc_now():
    return datetime.now(timezone.utc)


def json_response(payload=None, status_code=200, **fields):
    body = dict(payload or {})
    body.update(fields)
    response = jsonify(body)
    return response if status_code == 200 else (response, status_code)


def json_success(status_code=200, **fields):
    return json_response({"success": True}, status_code=status_code, **fields)


def json_error(error, status_code=400, **fields):
    return json_response({"success": False, "error": error}, status_code=status_code, **fields)


def ensure_utc_datetime(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def normalize_coding_ninjas_profile_id(value):
    """Return the Code360 public profile id from a username, UUID, or profile URL."""
    value = (value or "").strip()
    if not value:
        return ""
    match = re.search(
        r"(?:naukri\.com/code360/profile/|codingninjas\.com/(?:studio|codestudio)/profile/)([^/?#]+)",
        value,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return value.rstrip("/").split("/")[-1].strip()


def platform_name_filter(url):
    if not url:
        return None
    url = url.lower()
    if "leetcode.com" in url:
        return "LeetCode"
    if "geeksforgeeks.org" in url:
        return "GFG"
    if "codingninjas.com" in url or "naukri.com/code360" in url:
        return "Coding Ninjas"
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    if "hackerrank.com" in url:
        return "HackerRank"
    return "Link"


def platform_color_filter(name):
    colors = {
        "LeetCode": "warning text-dark",
        "GFG": "success",
        "Coding Ninjas": "danger",
        "YouTube": "danger",
        "HackerRank": "success",
    }
    return colors.get(name, "primary")


def parse_search_query(raw_query):
    return search_service.parse_search_query(raw_query)


def tokenize_search_text(value):
    return search_service.tokenize_search_text(value)


def build_external_searches(query, requested_platforms=None):
    return search_service.build_external_searches(query, requested_platforms)


def question_links(question):
    return search_service.question_links(question)


def search_dsa_questions(raw_query, limit=40):
    return search_service.search_dsa_questions(raw_query, limit=limit, db_handle=db)


EXTERNAL_SOLVED_TOTAL_KEYS = ("LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder")


def compute_total_solved(progress, external_totals, all_questions=None):
    progress = progress or {}
    if all_questions is not None:
        solved_items = {question_id: item for question_id, item in progress.items() if item.get("done")}
        platforms = compute_user_platforms(solved_items, external_totals or {}, all_questions)
        return sum(max(value, 0) for value in platforms.values())

    dsa_done = sum(1 for progress_item in progress.values() if progress_item.get("done"))
    external_total = sum(max(value, 0) for key, value in (external_totals or {}).items() if key in EXTERNAL_SOLVED_TOTAL_KEYS)
    return max(dsa_done, external_total)


def compute_c_score(user_doc, all_questions=None):
    """Compute composite C-Score (0-999) for a user document."""
    progress = user_doc.get("progress", {})
    dsa_done = sum(1 for progress_item in progress.values() if progress_item.get("done"))

    ext = user_doc.get("external_totals", {})
    lc_total = max(ext.get("LeetCode", 0), 0)
    lc_easy = max(ext.get("LeetCode_Easy", 0), 0)
    lc_medium = max(ext.get("LeetCode_Medium", 0), 0)
    lc_hard = max(ext.get("LeetCode_Hard", 0), 0)
    lc_rating = max(ext.get("LeetCode_Rating", 0), 0)
    gfg_total = max(ext.get("GFG", 0), 0)
    hr_total = max(ext.get("HackerRank", 0), 0)
    cn_total = max(ext.get("Coding Ninjas", 0), 0)
    external_total = sum(max(value, 0) for key, value in ext.items() if key in EXTERNAL_SOLVED_TOTAL_KEYS)

    ext_daily = user_doc.get("external_daily_counts", {})
    extra_progress_days = set()
    for progress_item in progress.values():
        timestamp = progress_item.get("timestamp")
        if not timestamp or not progress_item.get("done"):
            continue
        if isinstance(timestamp, str):
            day_key = timestamp[:10]
        else:
            day_key = timestamp.date().isoformat()
        if day_key not in ext_daily:
            extra_progress_days.add(day_key)
    active_days = len(ext_daily) + len(extra_progress_days)

    s_dsa = min(dsa_done / 450, 1.0) * 250
    s_lc_total = min(lc_total / 500, 1.0) * 200
    s_lc_diff = min((lc_easy * 1 + lc_medium * 3 + lc_hard * 6) / 1500, 1.0) * 150
    s_lc_rating = min(lc_rating / 2500, 1.0) * 200
    s_other = min((gfg_total + hr_total + cn_total) / 300, 1.0) * 100
    s_consistency = min(active_days / 365, 1.0) * 100

    c_score = int(round(s_dsa + s_lc_total + s_lc_diff + s_lc_rating + s_other + s_consistency))
    c_score = min(c_score, 999)

    global_total = compute_total_solved(progress, ext, all_questions) if all_questions is not None else max(dsa_done, external_total)

    return {
        "c_score": c_score,
        "dsa_done": dsa_done,
        "lc_total": lc_total,
        "lc_easy": lc_easy,
        "lc_medium": lc_medium,
        "lc_hard": lc_hard,
        "lc_rating": lc_rating,
        "gfg_total": gfg_total,
        "hr_total": hr_total,
        "cn_total": cn_total,
        "active_days": active_days,
        "total_solved": global_total,
    }


def compute_user_platforms(solved_items, external_totals, all_questions):
    """Compute platform counts combining solved DSA questions with external totals."""
    platforms = {"LeetCode": 0, "GFG": 0, "Coding Ninjas": 0, "HackerRank": 0, "AtCoder": 0, "Other": 0}
    
    for question in all_questions:
        question_id = str(question.get("_id", ""))
        if question_id in solved_items:
            url = (question.get("url") or "").lower()
            if "leetcode.com" in url:
                platforms["LeetCode"] += 1
            elif "geeksforgeeks.org" in url:
                platforms["GFG"] += 1
            elif "codingninjas.com" in url or "naukri.com/code360" in url:
                platforms["Coding Ninjas"] += 1
            elif "hackerrank.com" in url:
                platforms["HackerRank"] += 1
            else:
                platforms["Other"] += 1

    ext_totals = external_totals or {}
    platforms["LeetCode"] = max(platforms["LeetCode"], ext_totals.get("LeetCode", 0), 0)
    platforms["GFG"] = max(platforms["GFG"], ext_totals.get("GFG", 0), 0)
    platforms["Coding Ninjas"] = max(platforms["Coding Ninjas"], ext_totals.get("Coding Ninjas", 0), 0)
    platforms["HackerRank"] = max(platforms["HackerRank"], ext_totals.get("HackerRank", 0), 0)
    platforms["AtCoder"] = max(ext_totals.get("AtCoder", 0), 0)

    return platforms
