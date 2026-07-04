from flask import current_app
from app.extensions import cache, db
from app.leaderboard.cache import LEADERBOARD_CACHE_TIMEOUT, leaderboard_snapshot_cache_key
from app.utils import compute_c_score


def build_leaderboard_data():
    """Query all users and compute leaderboard rankings."""
    users = list(
        db.user.find(
            {"is_deactivated": {"$ne": True}},
            {
                "name": 1,
                "email": 1,
                "profile_photo": 1,
                "college": 1,
                "leetcode_username": 1,
                "github_username": 1,
                "gfg_username": 1,
                "hackerrank_username": 1,
                "codingninjas_username": 1,
                "progress": 1,
                "external_totals": 1,
                "external_daily_counts": 1,
                "platform_calendars": 1,
            },
        )
    )

    try:
        pre = current_app.config.get("_PRECOMPUTED")
    except RuntimeError:
        pre = None
    all_questions = pre["all_questions"] if pre else list(db.question.find({}, {"url": 1}))
    entries = []
    for user in users:
        name = user.get("name", "Anonymous")
        if not name or name.strip() == "":
            continue
        stats = compute_c_score(user, all_questions=all_questions)
        entries.append(
            {
                "user_id": str(user["_id"]),
                "name": name,
                "profile_photo": user.get("profile_photo", ""),
                "college": user.get("college", ""),
                "leetcode_username": user.get("leetcode_username", ""),
                "codingninjas_username": user.get("codingninjas_username", ""),
                **stats,
            }
        )

    return entries


def sort_leaderboard_entries_by_c_score(entries=None):
    """Return entries sorted by the same C-Score ordering used on the leaderboard."""
    entries = entries if entries is not None else build_leaderboard_data()
    return sorted(entries, key=lambda item: item["c_score"], reverse=True)


def get_user_rank_by_c_score(user_id, entries=None):
    """Return the one-based local leaderboard rank for the given user id."""
    if not user_id:
        return None

    ranked_entries = sort_leaderboard_entries_by_c_score(entries)
    user_id = str(user_id)

    for index, entry in enumerate(ranked_entries, start=1):
        if entry.get("user_id") == user_id:
            return index

    return None


def build_college_leaderboard_data(entries=None):
    """Aggregate user leaderboard entries into college rankings."""
    entries = entries if entries is not None else build_leaderboard_data()
    colleges = {}

    for entry in entries:
        college = (entry.get("college") or "").strip()
        if not college:
            continue

        college_entry = colleges.setdefault(
            college.lower(),
            {
                "college": college,
                "member_count": 0,
                "c_score": 0,
                "total_solved": 0,
                "dsa_done": 0,
                "lc_total": 0,
                "gfg_total": 0,
                "cn_total": 0,
                "hr_total": 0,
                "lc_rating_total": 0,
                "rated_member_count": 0,
                "top_user": None,
            },
        )

        college_entry["member_count"] += 1
        college_entry["c_score"] += entry.get("c_score", 0)
        college_entry["total_solved"] += entry.get("total_solved", 0)
        college_entry["dsa_done"] += entry.get("dsa_done", 0)
        college_entry["lc_total"] += entry.get("lc_total", 0)
        college_entry["gfg_total"] += entry.get("gfg_total", 0)
        college_entry["cn_total"] += entry.get("cn_total", 0)
        college_entry["hr_total"] += entry.get("hr_total", 0)

        lc_rating = entry.get("lc_rating", 0)
        if lc_rating:
            college_entry["lc_rating_total"] += lc_rating
            college_entry["rated_member_count"] += 1

        top_user = college_entry["top_user"]
        if top_user is None or entry.get("c_score", 0) > top_user.get("c_score", 0):
            college_entry["top_user"] = {
                "name": entry.get("name", "Anonymous"),
                "c_score": entry.get("c_score", 0),
                "profile_photo": entry.get("profile_photo", ""),
            }

    college_entries = []
    for college_entry in colleges.values():
        rated_count = college_entry.pop("rated_member_count")
        rating_total = college_entry.pop("lc_rating_total")
        college_entry["lc_rating"] = round(rating_total / rated_count) if rated_count else 0
        college_entry["user_id"] = ""
        college_entry["name"] = college_entry["college"]
        college_entry["profile_photo"] = ""
        college_entries.append(college_entry)

    return sorted(
        college_entries,
        key=lambda item: (item["c_score"], item["total_solved"], item["member_count"]),
        reverse=True,
    )


def _assign_ranks(entries, key):
    for index, entry in enumerate(entries, start=1):
        entry[f"rank_{key}"] = index
    return entries


def build_leaderboard_snapshots(entries=None):
    entries = entries if entries is not None else build_leaderboard_data()
    by_cscore = _assign_ranks(sort_leaderboard_entries_by_c_score([dict(entry) for entry in entries]), "cscore")
    by_questions = _assign_ranks(
        sorted((dict(entry) for entry in entries), key=lambda item: item["total_solved"], reverse=True),
        "questions",
    )
    by_rating = _assign_ranks(
        sorted((dict(entry) for entry in entries), key=lambda item: item["lc_rating"], reverse=True),
        "rating",
    )
    by_college = _assign_ranks(build_college_leaderboard_data([dict(entry) for entry in entries]), "college")
    return {
        "entries": entries,
        "by_cscore": by_cscore,
        "by_questions": by_questions,
        "by_rating": by_rating,
        "by_college": by_college,
    }


def get_leaderboard_snapshots():
    key = leaderboard_snapshot_cache_key()
    try:
        cached = cache.get(key)
    except KeyError:
        cached = None
    if cached is not None:
        return cached

    snapshot = build_leaderboard_snapshots()
    try:
        cache.set(key, snapshot, timeout=LEADERBOARD_CACHE_TIMEOUT)
    except KeyError:
        pass
    return snapshot
