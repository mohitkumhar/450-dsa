import re
from urllib.parse import quote_plus, urlparse

from bson import ObjectId
from bson.errors import InvalidId

from app.extensions import db


from app.platforms.metadata import PLATFORM_META


def parse_search_query(raw_query):
    """Return cleaned query text and platform names mentioned by the user."""
    query = (raw_query or "").strip()
    query_l = query.lower()
    requested_platforms = []

    for platform_name, meta in PLATFORM_META.items():
        if not meta.get("search_url"):
            continue
        platform_requested = False
        for alias in meta["aliases"]:
            pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
            if re.search(pattern, query_l):
                platform_requested = True
                query = re.sub(pattern, " ", query, flags=re.IGNORECASE)
                query_l = query.lower()
        if platform_requested:
            requested_platforms.append(platform_name)

    cleaned = re.sub(r"\s+", " ", query).strip()
    return cleaned, requested_platforms


def tokenize_search_text(value):
    return [token for token in re.split(r"[^a-z0-9]+", (value or "").lower()) if token]


def build_external_searches(query, requested_platforms=None):
    searchable_platforms = [p for p, m in PLATFORM_META.items() if m.get("search_url")]
    platforms = requested_platforms or searchable_platforms
    encoded = quote_plus(query)
    return [
        {
            "platform": platform,
            "url": PLATFORM_META[platform]["search_url"].format(query=encoded),
            "color": platform_badge_id(platform),
        }
        for platform in platforms
        if platform in PLATFORM_META and PLATFORM_META[platform].get("search_url") and query
    ]


def normalize_editorial_links(raw_links):
    """Return safe, labeled editorial links for a question document."""
    if not raw_links:
        return []
    if isinstance(raw_links, str):
        raw_links = [{"label": "Editorial", "url": raw_links}]

    links = []
    for index, item in enumerate(raw_links, start=1):
        if isinstance(item, str):
            label = f"Editorial {index}"
            url = item
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("title") or f"Editorial {index}").strip()
            url = str(item.get("url") or "").strip()
        else:
            continue

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        links.append({"label": label or f"Editorial {index}", "url": url})
    return links


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
                "color": platform_badge_id(platform),
            }
        )
    return links


def question_editorial_links(question):
    return normalize_editorial_links(question.get("editorial_links") or question.get("editorials"))


def platform_badge_id(platform):
    badge_class = PLATFORM_META.get(platform, {}).get("badge_class", "badge-link")
    return badge_class.removeprefix("badge-")


PLATFORM_FILTER_MAP = {
    meta["id"]: name
    for name, meta in PLATFORM_META.items()
    if meta.get("search_url")
}
PLATFORM_FILTER_MAP.update(
    {
        platform_badge_id(name): name
        for name, meta in PLATFORM_META.items()
        if meta.get("search_url")
    }
)

PLATFORM_URL_KEYWORDS = {
    name: "|".join(re.escape(domain) for domain in meta["domains"])
    for name, meta in PLATFORM_META.items()
    if meta.get("search_url") and meta.get("domains")
}

DIFFICULTY_FILTERS = {
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}


def search_dsa_questions(raw_query, limit=40, db_handle=None, filters=None, progress=None):
    db_handle = db_handle or db
    filters = filters or {}
    progress = progress or {}
    query, requested_platforms = parse_search_query(raw_query)
    query_tokens = tokenize_search_text(query)
    topic_id_str = filters.get("topic_id", "")
    difficulty_filter = filters.get("difficulty", "")
    platform_filter = filters.get("platform", "")
    status_filter = filters.get("status", "")
    has_filters = any((topic_id_str, difficulty_filter, platform_filter, status_filter))

    def empty_payload():
        return {
            "query": query,
            "requested_platforms": requested_platforms,
            "results": [],
            "external_searches": [],
        }

    if not query_tokens and not has_filters:
        return empty_payload()

    mongo_query = {}
    if query_tokens:
        mongo_query["$text"] = {"$search": query}

    if topic_id_str:
        try:
            mongo_query["topic"] = ObjectId(topic_id_str)
        except InvalidId:
            return empty_payload()

    platform_name = PLATFORM_FILTER_MAP.get(platform_filter, "")
    if platform_name:
        url_keyword = PLATFORM_URL_KEYWORDS.get(platform_name, "")
        if url_keyword:
            mongo_query["$or"] = [
                {"url": {"$regex": url_keyword, "$options": "i"}},
                {"url2": {"$regex": url_keyword, "$options": "i"}},
            ]

    if status_filter in ("done", "bookmarked"):
        flag = "done" if status_filter == "done" else "bookmark"
        ids = [question_id for question_id, item in progress.items() if item.get(flag)]
        if not ids:
            return empty_payload()
        try:
            mongo_query["_id"] = {"$in": [ObjectId(question_id) for question_id in ids]}
        except InvalidId:
            return empty_payload()

    projection = {"problem": 1, "topic": 1, "url": 1, "url2": 1, "editorial_links": 1}
    post_fetch_filters = bool(
        requested_platforms
        or difficulty_filter in DIFFICULTY_FILTERS
        or status_filter == "undone"
    )
    fetch_limit = None if requested_platforms else (limit * 4 if post_fetch_filters else limit)
    if difficulty_filter in DIFFICULTY_FILTERS:
        projection["difficulty"] = 1

    if query_tokens:
        projection["score"] = {"$meta": "textScore"}
        cursor = db_handle.question.find(mongo_query, projection).sort([("score", {"$meta": "textScore"})])
    else:
        cursor = db_handle.question.find(mongo_query, projection)

    if fetch_limit is not None:
        cursor = cursor.limit(fetch_limit)

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
        q_id_str = str(question["_id"])
        topic_doc = topics.get(question.get("topic"), {})
        problem = question.get("problem", "")
        topic_name = topic_doc.get("name", "Unknown")
        links = question_links(question)
        progress_item = progress.get(q_id_str, {})

        if requested_platforms and not any(link["platform"] in requested_platforms for link in links):
            continue

        if difficulty_filter in DIFFICULTY_FILTERS:
            if question.get("difficulty", "Medium") != DIFFICULTY_FILTERS[difficulty_filter]:
                continue

        if status_filter == "undone" and progress_item.get("done"):
            continue

        results.append(
            {
                "id": q_id_str,
                "problem": problem,
                "topic": topic_name,
                "topic_id": str(question.get("topic")),
                "topic_position": topic_doc.get("position", 999),
                "links": links,
                "editorial_links": question_editorial_links(question),
                "external_searches": build_external_searches(problem, requested_platforms),
                "score": question.get("score", 0),
                "done": progress_item.get("done", False),
                "bookmarked": progress_item.get("bookmark", False),
            }
        )

    return {
        "query": query,
        "requested_platforms": requested_platforms,
        "results": results[:limit],
        "external_searches": build_external_searches(query, requested_platforms),
    }


def platform_name_filter(url):
    if not url:
        return None
    url = url.lower()
    for meta in PLATFORM_META.values():
        for domain in meta["domains"]:
            if domain in url:
                return meta["name"]
    return "Link"


