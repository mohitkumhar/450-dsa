import re
from urllib.parse import quote_plus

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


def search_dsa_questions(raw_query, limit=40, db_handle=None):
    db_handle = db_handle or db
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
        db_handle.question.find(
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
    topic_ids = list({question.get("topic") for question in questions if question.get("topic")})
    topics = (
        {
            topic["_id"]: topic
            for topic in db_handle.topic.find({"_id": {"$in": topic_ids}}, {"name": 1, "position": 1})
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

        if requested_platforms and not any(link["platform"] in requested_platforms for link in links):
            continue

        results.append(
            {
                "id": str(question["_id"]),
                "problem": problem,
                "topic": topic_name,
                "topic_id": str(question.get("topic")),
                "topic_position": topic_doc.get("position", 999),
                "links": links,
                "external_searches": build_external_searches(problem, requested_platforms),
                "score": question.get("score", 0),
            }
        )

    return {
        "query": query,
        "requested_platforms": requested_platforms,
        "results": results,
        "external_searches": build_external_searches(query, requested_platforms),
    }


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
