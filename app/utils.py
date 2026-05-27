import re
from math import isfinite
from datetime import datetime, timezone

from flask import jsonify

from app.extensions import db
from app.platforms.metadata import PLATFORM_META
from app.search import service as search_service
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

from app.extensions import db
import requests
from typing import Dict, List, Optional, Any
import hashlib
import hmac

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


EXTERNAL_SOLVED_TOTAL_KEYS = ("LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder")
PLATFORM_COUNT_KEYS = ("LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder", "Other")


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
    external_total = sum(
        coerce_non_negative_number(value)
        for key, value in ext.items()
        if key in EXTERNAL_SOLVED_TOTAL_KEYS
    )

    ext_daily = user_doc.get("external_daily_counts", {})
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

    return platforms
# ========== DISCORD WEBHOOK UTILITIES ==========

# Discord webhook URL validation pattern
DISCORD_WEBHOOK_PATTERN = re.compile(
    r'^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/(\d+)/([\w-]+)$'
)

def validate_discord_webhook_url(url: str) -> bool:
    """Validate if a URL is a proper Discord webhook URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(DISCORD_WEBHOOK_PATTERN.match(url.strip()))

def test_discord_webhook(url: str) -> Dict[str, Any]:
    """Test a Discord webhook by sending a test message."""
    if not validate_discord_webhook_url(url):
        return {"success": False, "error": "Invalid Discord webhook URL format"}
    
    test_data = {
        "content": "✅ Webhook configured successfully! This is a test message from 450 DSA Tracker.",
        "embeds": [{
            "title": "Webhook Test",
            "description": "Your Discord integration is working correctly!",
            "color": 0x00ff00,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    
    try:
        response = requests.post(url, json=test_data, timeout=10)
        if response.status_code == 204:
            return {"success": True, "message": "Webhook test successful!"}
        else:
            return {"success": False, "error": f"Discord returned status {response.status_code}: {response.text[:100]}"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Connection timeout - Discord may be slow"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection failed - check your internet"}
    except Exception as e:
        return {"success": False, "error": f"Error: {str(e)}"}

def send_discord_webhook(
    webhook_url: str,
    title: str,
    description: str,
    color: int = 0x5865F2,  # Discord blurple color
    fields: Optional[List[Dict[str, Any]]] = None,
    thumbnail_url: Optional[str] = None,
    footer_text: Optional[str] = None
) -> Dict[str, Any]:
    """Send a rich embed message to Discord webhook.
    
    Args:
        webhook_url: Discord webhook URL
        title: Embed title
        description: Embed description
        color: Embed color (hex code as integer)
        fields: List of {"name": str, "value": str, "inline": bool}
        thumbnail_url: URL for thumbnail image
        footer_text: Footer text
    
    Returns:
        Dict with success status and message
    """
    if not validate_discord_webhook_url(webhook_url):
        return {"success": False, "error": "Invalid Discord webhook URL"}
    
    embed = {
        "title": title[:256],  # Discord limit
        "description": description[:4096],
        "color": color,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if fields:
        embed["fields"] = [f for f in fields[:25]]  # Max 25 fields
    
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}
    
    if footer_text:
        embed["footer"] = {"text": footer_text[:2048]}
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            return {"success": True, "message": "Notification sent successfully"}
        else:
            return {"success": False, "error": f"Discord error: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to send: {str(e)}"}

def format_milestone_message(user_name: str, milestone: int, total_solved: int) -> Dict[str, Any]:
    """Format a milestone achievement message.
    
    Args:
        user_name: User's display name
        milestone: Milestone number (50, 100, 200)
        total_solved: Total questions solved
    
    Returns:
        Dict with title, description, and color
    """
    return {
        "title": f"🎉 Milestone Achieved! 🎉",
        "description": f"**{user_name}** has reached **{milestone}** problems solved!\n"
                      f"Total solved: **{total_solved}** / 450\n"
                      f"Keep up the great work! 💪",
        "color": 0xFFD700  # Gold color
    }

def format_leaderboard_message(rank: int, user_name: str, c_score: int) -> Dict[str, Any]:
    """Format a leaderboard top 10 message."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    medal = medals.get(rank, f"#{rank}")
    
    return {
        "title": f"🏆 Leaderboard Update! 🏆",
        "description": f"{medal} **{user_name}** has entered the top {min(rank, 10)}!\n"
                      f"C-Score: **{c_score}**",
        "color": 0x5865F2  # Discord blurple
    }

def format_weekly_challenge_message(challenge_name: str, description: str, end_date: datetime) -> Dict[str, Any]:
    """Format a weekly challenge message."""
    return {
        "title": f"📢 New Weekly Challenge: {challenge_name}",
        "description": f"{description}\n\n"
                      f"⏰ Ends: {end_date.strftime('%B %d, %Y at %I:%M %p UTC')}",
        "color": 0x00ff00  # Green
    }

def format_cohort_progress_message(cohort_name: str, completion_percent: float, active_members: int) -> Dict[str, Any]:
    """Format a cohort progress update message."""
    return {
        "title": f"📊 Cohort Update: {cohort_name}",
        "description": f"Cohort progress: **{completion_percent:.1f}%** complete!\n"
                      f"Active members: **{active_members}**\n"
                      f"Keep up the momentum! 🚀",
        "color": 0x9B59B6  # Purple
    }
    # ========== WEBHOOK TRIGGER FUNCTIONS ==========
def trigger_discord_event(event_type: str, event_data: dict):
    """Trigger a Discord webhook for an event.
    
    This function should be called whenever a relevant event occurs:
    - milestone: When a user reaches 50/100/200 solved
    - leaderboard_top10: When a user enters top 10
    - weekly_challenge: When a new challenge is posted
    - cohort_progress: When a cohort reaches a milestone
    """
    from app.discord_webhook import DiscordWebhookConfig
    
    # Get active webhooks for this event
    webhooks = DiscordWebhookConfig.get_active_for_event(event_type)
    
    if not webhooks:
        return {"success": True, "message": "No webhooks configured for this event"}
    
    # Format message based on event type
    if event_type == "milestone":
        message = format_milestone_message(
            event_data.get("user_name", "A user"),
            event_data.get("milestone", 0),
            event_data.get("total_solved", 0)
        )
    elif event_type == "leaderboard_top10":
        message = format_leaderboard_message(
            event_data.get("rank", 0),
            event_data.get("user_name", "A user"),
            event_data.get("c_score", 0)
        )
    elif event_type == "weekly_challenge":
        message = format_weekly_challenge_message(
            event_data.get("challenge_name", "New Challenge"),
            event_data.get("description", ""),
            event_data.get("end_date", datetime.utcnow())
        )
    elif event_type == "cohort_progress":
        message = format_cohort_progress_message(
            event_data.get("cohort_name", "Cohort"),
            event_data.get("completion_percent", 0),
            event_data.get("active_members", 0)
        )
    else:
        return {"success": False, "error": f"Unknown event type: {event_type}"}
    
    # Send to all configured webhooks
    results = []
    for webhook in webhooks:
        result = send_discord_webhook(
            webhook["webhook_url"],
            message["title"],
            message["description"],
            message["color"]
        )
        results.append(result)
    
    return {"success": True, "results": results}