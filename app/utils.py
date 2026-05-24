import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

from flask import jsonify

from app.extensions import db


PLATFORM_SEARCHES = {
    "LeetCode": {
        "aliases": ("lc", "leetcode", "leet code"),
        "color": "lc",
        "url": "https://duckduckgo.com/?q=site%3Aleetcode.com%2Fproblems+{query}",
    },
    "GFG": {
        "aliases": ("gfg", "geeksforgeeks", "geeks for geeks"),
        "color": "gfg",
        "url": "https://duckduckgo.com/?q=site%3Ageeksforgeeks.org%2Fproblems+{query}",
    },
    "Coding Ninjas": {
        "aliases": ("cn", "coding ninjas", "codingninjas", "code360", "naukri code360"),
        "color": "cn",
        "url": "https://duckduckgo.com/?q=%28site%3Anaukri.com%2Fcode360%2Fproblems+OR+site%3Acodingninjas.com%2Fcodestudio%2Fproblems%29+{query}",
    },
    "HackerRank": {
        "aliases": ("hr", "hackerrank", "hacker rank"),
        "color": "hr",
        "url": "https://duckduckgo.com/?q=site%3Ahackerrank.com%2Fchallenges+{query}",
    },
}


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
    """Return cleaned query text and platform names mentioned by the user."""
    query = (raw_query or "").strip()
    query_l = query.lower()
    requested_platforms = []

    for platform, meta in PLATFORM_SEARCHES.items():
        platform_requested = False
        for alias in meta["aliases"]:
            pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
            if re.search(pattern, query_l):
                platform_requested = True
                query = re.sub(pattern, " ", query, flags=re.IGNORECASE)
                query_l = query.lower()
        if platform_requested:
            requested_platforms.append(platform)

    cleaned = re.sub(r"\s+", " ", query).strip()
    return cleaned, requested_platforms


def tokenize_search_text(value):
    return [token for token in re.split(r"[^a-z0-9]+", (value or "").lower()) if token]


def build_external_searches(query, requested_platforms=None):
    platforms = requested_platforms or list(PLATFORM_SEARCHES.keys())
    encoded = quote_plus(query)
    return [
        {
            "platform": platform,
            "url": PLATFORM_SEARCHES[platform]["url"].format(query=encoded),
            "color": PLATFORM_SEARCHES[platform]["color"],
        }
        for platform in platforms
        if platform in PLATFORM_SEARCHES and query
    ]


def question_links(question):
    links = []
    for field in ("url", "url2"):
        url = question.get(field)
        if not url:
            continue
        platform = platform_name_filter(url)
        links.append(
            {
                "platform": platform,
                "url": url,
                "color": PLATFORM_SEARCHES.get(platform, {}).get("color", "link"),
            }
        )
    return links


def search_dsa_questions(raw_query, limit=40):
    query, requested_platforms = parse_search_query(raw_query)
    query_tokens = tokenize_search_text(query)
    if not query_tokens:
        return {
            "query": query,
            "requested_platforms": requested_platforms,
            "results": [],
            "external_searches": [],
        }

    cursor = (
        db.question.find(
            {"$text": {"$search": query}},
            {
                "problem": 1,
                "topic": 1,
                "url": 1,
                "url2": 1,
                "score": {"$meta": "textScore"},
            },
        )
        .sort([("score", {"$meta": "textScore"})])
        .limit(limit)
    )
    questions = list(cursor)
    topic_ids = list(
        {question.get("topic") for question in questions if question.get("topic")}
    )
    topics = (
        {
            topic["_id"]: topic
            for topic in db.topic.find(
                {"_id": {"$in": topic_ids}}, {"name": 1, "position": 1}
            )
        }
        if topic_ids
        else {}
    )

    results = []
    for question in questions:
        topic_doc = topics.get(question.get("topic"), {})
        problem = question.get("problem", "")
        topic_name = topic_doc.get("name", "Unknown")
        links = question_links(question)

        if requested_platforms and not any(
            link["platform"] in requested_platforms for link in links
        ):
            continue

        results.append(
            {
                "id": str(question["_id"]),
                "problem": problem,
                "topic": topic_name,
                "topic_id": str(question.get("topic")),
                "topic_position": topic_doc.get("position", 999),
                "links": links,
                "external_searches": build_external_searches(
                    problem, requested_platforms
                ),
                "score": question.get("score", 0),
            }
        )

    return {
        "query": query,
        "requested_platforms": requested_platforms,
        "results": results,
        "external_searches": build_external_searches(query, requested_platforms),
    }


EXTERNAL_SOLVED_TOTAL_KEYS = ("LeetCode", "GFG", "Coding Ninjas", "HackerRank", "AtCoder")


def compute_total_solved(progress, external_totals, all_questions=None):
    solved_items = {question_id: item for question_id, item in (progress or {}).items() if item.get("done")}
    if all_questions is not None:
        platforms = compute_user_platforms(solved_items, external_totals or {}, all_questions)
        return sum(max(value, 0) for value in platforms.values())

    dsa_done = len(solved_items)
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

    ext_daily = user_doc.get("external_daily_counts", {})
    daily_dates = set(ext_daily.keys()) if ext_daily else set()
    for progress_item in progress.values():
        timestamp = progress_item.get("timestamp")
        if timestamp and progress_item.get("done"):
            daily_dates.add(timestamp.strftime("%Y-%m-%d"))
    active_days = len(daily_dates)

    s_dsa = min(dsa_done / 450, 1.0) * 250
    s_lc_total = min(lc_total / 500, 1.0) * 200
    s_lc_diff = min((lc_easy * 1 + lc_medium * 3 + lc_hard * 6) / 1500, 1.0) * 150
    s_lc_rating = min(lc_rating / 2500, 1.0) * 200
    s_other = min((gfg_total + hr_total + cn_total) / 300, 1.0) * 100
    s_consistency = min(active_days / 365, 1.0) * 100

    c_score = int(round(s_dsa + s_lc_total + s_lc_diff + s_lc_rating + s_other + s_consistency))
    c_score = min(c_score, 999)

    global_total = compute_total_solved(progress, ext, all_questions)

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
