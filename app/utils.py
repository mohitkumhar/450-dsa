import re
from math import isfinite
from datetime import date, datetime, timezone

from flask import jsonify

from app.extensions import db
from app.platforms.metadata import PLATFORM_META
from app.search import service as search_service


def utc_now():
    return datetime.now(timezone.utc)


def normalize_timestamp(timestamp):
    """Convert a progress timestamp to a date string (YYYY-MM-DD).

    Accepts datetime, date, or ISO-format string.  Returns None for
    unparseable or missing values so callers can skip the entry safely.
    """
    if isinstance(timestamp, datetime):
        return timestamp.strftime("%Y-%m-%d")
    if isinstance(timestamp, date):
        return timestamp.isoformat()
    if isinstance(timestamp, str):
        try:
            return date.fromisoformat(timestamp[:10]).isoformat()
        except (ValueError, TypeError):
            return None
    return None


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
    for meta in PLATFORM_META.values():
        for domain in meta["domains"]:
            if domain in url:
                return meta["name"]
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


def platform_profile_url(username, platform):
    if not username:
        return "#"
    platform = platform.lower()
    if platform == "leetcode":
        return f"https://leetcode.com/{username}"
    if platform == "gfg":
        return f"https://www.geeksforgeeks.org/user/{username}"
    if platform == "codingninjas" or platform == "coding ninjas":
        return f"https://www.naukri.com/code360/profile/{username}"
    if platform == "hackerrank":
        return f"https://www.hackerrank.com/{username}"
    if platform == "github":
        return f"https://github.com/{username}"
    if platform == "atcoder":
        return f"https://atcoder.jp/users/{username}"
    if platform == "codewars":
        return f"https://www.codewars.com/users/{username}"
    return "#"


def safe_url_filter(url):
    if not url:
        return "#"
    url_stripped = url.strip()
    # Allow http/https only
    if url_stripped.lower().startswith(("http://", "https://")):
        return url_stripped
    # If the URL contains other scheme characters like ':' or similar, reject it
    # to avoid javascript:, data:, or any custom protocols
    if ":" in url_stripped and not url_stripped.lower().startswith(("http://", "https://")):
        return "#"
    # If the url starts with //, prepend https:
    if url_stripped.startswith("//"):
        return "https:" + url_stripped
    # Otherwise, treat it as a path/domain and prepend https://
    return "https://" + url_stripped


def parse_search_query(raw_query):
    return search_service.parse_search_query(raw_query)


def tokenize_search_text(value):
    return search_service.tokenize_search_text(value)


def build_external_searches(query, requested_platforms=None):
    return search_service.build_external_searches(query, requested_platforms)


def question_links(question):
    return search_service.question_links(question)


def question_editorial_links(question):
    return search_service.question_editorial_links(question)


def search_dsa_questions(raw_query, limit=40):
    return search_service.search_dsa_questions(raw_query, limit=limit, db_handle=db)


EXTERNAL_SOLVED_TOTAL_KEYS = ("LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder", "Codewars")
PLATFORM_COUNT_KEYS = ("LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder", "Codewars", "Other")


def empty_platform_counts():
    return {platform: 0 for platform in PLATFORM_COUNT_KEYS}


def platform_from_question_url(url):
    """Return the tracked platform bucket for a question URL."""
    url = (url or "").lower()
    if "leetcode.com" in url:
        return "LeetCode"
    if "geeksforgeeks.org" in url:
        return "GFG"
    if "codingninjas.com" in url or "naukri.com/code360" in url:
        return "Coding Ninjas"
    if "hackerrank.com" in url:
        return "HackerRank"
    if "atcoder.jp" in url:
        return "AtCoder"
    return "Other"


def coerce_non_negative_number(value):
    """Return a safe finite non-negative numeric value for persisted stats."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return value if isfinite(value) and value > 0 else 0
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            parsed = float(stripped)
        except ValueError:
            return 0
        return parsed if isfinite(parsed) and parsed > 0 else 0
    return 0


def count_valid_external_daily_entries(external_daily_counts):
    if not isinstance(external_daily_counts, dict):
        return 0
    return sum(1 for value in external_daily_counts.values() if coerce_non_negative_number(value) > 0)


def valid_external_daily_keys(external_daily_counts):
    if not isinstance(external_daily_counts, dict):
        return set()
    return {
        day_key
        for day_key, value in external_daily_counts.items()
        if coerce_non_negative_number(value) > 0
    }


def compute_total_solved(progress, external_totals, all_questions=None):
    progress = progress or {}
    if all_questions is not None:
        solved_items = {question_id: item for question_id, item in progress.items() if item.get("done")}
        platforms = compute_user_platforms(solved_items, external_totals or {}, all_questions)
        return sum(coerce_non_negative_number(value) for value in platforms.values())

    dsa_done = sum(1 for progress_item in progress.values() if progress_item.get("done"))
    external_total = sum(
        coerce_non_negative_number(value)
        for key, value in (external_totals or {}).items()
        if key in EXTERNAL_SOLVED_TOTAL_KEYS
    )
    return max(dsa_done, external_total)


def _get_field(user_doc, name, default=None):
    """Get a field from a raw dict or a ``UserWrapper`` (Flask-Login) object."""
    if user_doc is None:
        return default
    try:
        return user_doc.get(name, default)
    except (TypeError, AttributeError):
        pass
    try:
        return getattr(user_doc, name)
    except AttributeError:
        return default


def get_merged_daily_counts(user_doc):
    """Return merged flat dict of daily counts, preferring per-platform data with legacy fallback.

    Uses the new ``platform_calendars`` dict (``{platform: {date: count}}``) when available.
    A special ``_legacy`` key stores the old combined totals during the migration period;
    for dates that overlap with real per-platform data the higher of the two values is kept
    (so non-migrated platform contributions are not lost).  Dates from the legacy
    ``external_daily_counts`` field are merged using ``max()`` so older cumulative history
    is not lost when per-platform calendars have partial coverage (e.g. limited API windows).

    Falls back entirely to ``external_daily_counts`` when no per-platform data exists.
    """
    platform_calendars = _get_field(user_doc, "platform_calendars", {})
    if isinstance(platform_calendars, dict) and platform_calendars:
        legacy_fallback = {}
        calendars = {}
        for key, value in platform_calendars.items():
            if key == "_legacy" and isinstance(value, dict):
                legacy_fallback = value
            else:
                calendars[key] = value

        merged = {}
        for _platform, counts in calendars.items():
            if isinstance(counts, dict):
                for date, count in counts.items():
                    safe = coerce_non_negative_number(count)
                    if safe > 0:
                        merged[date] = merged.get(date, 0) + safe

        for date, count in legacy_fallback.items():
            safe = coerce_non_negative_number(count)
            if safe > 0:
                merged[date] = max(merged.get(date, 0), safe)

        legacy = _get_field(user_doc, "external_daily_counts", {})
        if isinstance(legacy, dict):
            for date, count in legacy.items():
                safe = coerce_non_negative_number(count)
                if safe > 0:
                    merged[date] = max(merged.get(date, 0), safe)

        if merged:
            return merged
        return legacy if legacy else {}
    return _get_field(user_doc, "external_daily_counts", {})


def compute_c_score(user_doc, all_questions=None):
    """Compute composite C-Score (0-999) for a user document."""
    progress = user_doc.get("progress", {})
    dsa_done = sum(1 for progress_item in progress.values() if progress_item.get("done"))

    ext = user_doc.get("external_totals", {})
    if not isinstance(ext, dict):
        ext = {}
    lc_total = coerce_non_negative_number(ext.get("LeetCode", 0))
    lc_easy = coerce_non_negative_number(ext.get("LeetCode_Easy", 0))
    lc_medium = coerce_non_negative_number(ext.get("LeetCode_Medium", 0))
    lc_hard = coerce_non_negative_number(ext.get("LeetCode_Hard", 0))
    lc_rating = coerce_non_negative_number(ext.get("LeetCode_Rating", 0))
    gfg_total = coerce_non_negative_number(ext.get("GFG", 0))
    hr_total = coerce_non_negative_number(ext.get("HackerRank", 0))
    cn_total = coerce_non_negative_number(ext.get("Coding Ninjas", 0))
    cw_total = coerce_non_negative_number(ext.get("Codewars", 0))
    external_total = sum(
        coerce_non_negative_number(value)
        for key, value in ext.items()
        if key in EXTERNAL_SOLVED_TOTAL_KEYS
    )

    ext_daily = get_merged_daily_counts(user_doc)
    valid_external_days = count_valid_external_daily_entries(ext_daily)
    ext_daily_keys = valid_external_daily_keys(ext_daily)
    extra_progress_days = set()
    for progress_item in progress.values():
        timestamp = progress_item.get("timestamp")
        if not timestamp or not progress_item.get("done"):
            continue
        if isinstance(timestamp, str):
            day_key = timestamp[:10]
        else:
            day_key = timestamp.date().isoformat()
        if day_key not in ext_daily_keys:
            extra_progress_days.add(day_key)
    active_days = valid_external_days + len(extra_progress_days)

    s_dsa = min(dsa_done / 450, 1.0) * 250
    s_lc_total = min(lc_total / 500, 1.0) * 200
    s_lc_diff = min((lc_easy * 1 + lc_medium * 3 + lc_hard * 6) / 1500, 1.0) * 150
    s_lc_rating = min(lc_rating / 2500, 1.0) * 200
    s_other = min((gfg_total + hr_total + cn_total + cw_total) / 300, 1.0) * 100
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
        "cw_total": cw_total,
        "active_days": active_days,
        "total_solved": global_total,
    }

def compute_user_platforms(solved_items, external_totals, all_questions):
    """Compute platform counts combining solved DSA questions with external totals."""
    platforms = compute_in_sheet_platform_counts(solved_items, all_questions)
    return merge_platform_counts(platforms, external_totals)


def compute_in_sheet_platform_counts(solved_items, all_questions):
    platforms = empty_platform_counts()
    
    for question in all_questions:
        question_id = str(question.get("_id", ""))
        if question_id in solved_items:
            platforms[platform_from_question_url(question.get("url"))] += 1

    return platforms


def merge_platform_counts(in_sheet_counts, external_totals):
    platforms = empty_platform_counts()
    for platform, count in (in_sheet_counts or {}).items():
        if platform in platforms:
            platforms[platform] = max(int(count or 0), 0)

    ext_totals = external_totals if isinstance(external_totals, dict) else {}
    platforms["LeetCode"] = max(platforms["LeetCode"], coerce_non_negative_number(ext_totals.get("LeetCode", 0)))
    platforms["GFG"] = max(platforms["GFG"], coerce_non_negative_number(ext_totals.get("GFG", 0)))
    platforms["Coding Ninjas"] = max(
        platforms["Coding Ninjas"],
        coerce_non_negative_number(ext_totals.get("Coding Ninjas", 0)),
    )
    platforms["HackerRank"] = max(
        platforms["HackerRank"],
        coerce_non_negative_number(ext_totals.get("HackerRank", 0)),
    )
    platforms["AtCoder"] = max(platforms["AtCoder"], coerce_non_negative_number(ext_totals.get("AtCoder", 0)))
    platforms["Codewars"] = max(platforms["Codewars"], coerce_non_negative_number(ext_totals.get("Codewars", 0)))

    return platforms


def update_computed_stats(user_id, progress, db_handle, total_questions, user_doc=None):
    from streaks import compute_streak

    dsa_done = sum(1 for p in progress.values() if p.get("done"))
    dsa_progress = round((dsa_done / total_questions * 100) if total_questions > 0 else 0, 1)
    merged = get_merged_daily_counts(user_doc) if user_doc else None
    current_streak, longest_streak = compute_streak(progress, external_daily_counts=merged)

    db_handle.user.update_one(
        {"_id": user_id},
        {"$set": {
            "dsa_progress": dsa_progress,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
        }}
    )
