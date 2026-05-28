from flask import current_app
from app.extensions import db
from app.utils import (
    compute_c_score,
    coerce_non_negative_number,
    get_merged_daily_counts,
    compute_in_sheet_platform_counts,
    PLATFORM_COUNT_KEYS,
)


def get_cutoff_date(time_range):
    from datetime import datetime, timedelta, timezone
    if time_range == "weekly":
        return (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    elif time_range == "monthly":
        return (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    return None


def compute_period_stats(user_doc, cutoff_date, time_range, all_questions=None):
    """Compute period-specific statistics and C-Score for a user document."""
    progress = user_doc.get("progress", {}) or {}
    
    # 1. DSA questions solved in period
    period_progress = {}
    for qid, item in progress.items():
        if not item.get("done"):
            continue
        ts = item.get("timestamp")
        if not ts:
            continue
        if isinstance(ts, str):
            date_str = ts[:10]
        else:
            date_str = ts.date().isoformat()
        if date_str >= cutoff_date:
            period_progress[qid] = item

    dsa_done = len(period_progress)

    # 2. Daily active counts from platforms
    platform_calendars = user_doc.get("platform_calendars", {})
    lc_total = 0
    gfg_total = 0
    cn_total = 0
    hr_total = 0
    cw_total = 0
    active_days_set = set()

    if isinstance(platform_calendars, dict) and platform_calendars:
        for platform, counts in platform_calendars.items():
            if platform == "_legacy":
                continue
            if isinstance(counts, dict):
                for dt, cnt in counts.items():
                    if dt >= cutoff_date:
                        val = coerce_non_negative_number(cnt)
                        if val > 0:
                            active_days_set.add(dt)
                            p_lower = platform.lower()
                            if p_lower == "leetcode":
                                lc_total += val
                            elif p_lower == "gfg":
                                gfg_total += val
                            elif p_lower in ("codingninjas", "coding ninjas"):
                                cn_total += val
                            elif p_lower == "hackerrank":
                                hr_total += val
                            elif p_lower == "codewars":
                                cw_total += val
    else:
        # Fallback to external_daily_counts
        legacy = get_merged_daily_counts(user_doc) or {}
        if isinstance(legacy, dict):
            for dt, cnt in legacy.items():
                if dt >= cutoff_date:
                    val = coerce_non_negative_number(cnt)
                    if val > 0:
                        active_days_set.add(dt)
                        lc_total += val  # Treat legacy daily counts as lc_total as a general fallback

    # Add active days from in-sheet progress
    for item in period_progress.values():
        ts = item.get("timestamp")
        if ts:
            if isinstance(ts, str):
                date_str = ts[:10]
            else:
                date_str = ts.date().isoformat()
            active_days_set.add(date_str)

    active_days = len(active_days_set)

    # Calculate consistency score
    if time_range == "weekly":
        s_consistency = min(active_days / 7, 1.0) * 100
    elif time_range == "monthly":
        s_consistency = min(active_days / 30, 1.0) * 100
    else:
        s_consistency = min(active_days / 365, 1.0) * 100

    # Get LeetCode rating (current state snapshot)
    ext = user_doc.get("external_totals", {}) or {}
    lc_rating = coerce_non_negative_number(ext.get("LeetCode_Rating", 0))

    # C-Score components
    s_dsa = min(dsa_done / 450, 1.0) * 250
    s_lc_total = min(lc_total / 500, 1.0) * 200
    s_lc_rating = min(lc_rating / 2500, 1.0) * 200
    s_other = min((gfg_total + hr_total + cn_total + cw_total) / 300, 1.0) * 100

    c_score = int(round(s_dsa + s_lc_total + s_lc_rating + s_other + s_consistency))
    c_score = min(c_score, 999)

    # Total solved in period
    if all_questions is not None:
        in_sheet_platforms = compute_in_sheet_platform_counts(period_progress, all_questions)
        merged_platforms = {}
        for platform in PLATFORM_COUNT_KEYS:
            in_sheet_cnt = in_sheet_platforms.get(platform, 0)
            ext_cnt = 0
            p_lower = platform.lower()
            if p_lower == "leetcode":
                ext_cnt = lc_total
            elif p_lower == "gfg":
                ext_cnt = gfg_total
            elif p_lower in ("codingninjas", "coding ninjas"):
                ext_cnt = cn_total
            elif p_lower == "hackerrank":
                ext_cnt = hr_total
            elif p_lower == "codewars":
                ext_cnt = cw_total
            merged_platforms[platform] = max(in_sheet_cnt, ext_cnt)
        total_solved = sum(merged_platforms.values())
    else:
        total_solved = max(dsa_done, lc_total + gfg_total + cn_total + hr_total + cw_total)

    return {
        "c_score": c_score,
        "dsa_done": dsa_done,
        "lc_total": lc_total,
        "lc_easy": 0,
        "lc_medium": 0,
        "lc_hard": 0,
        "lc_rating": lc_rating,
        "gfg_total": gfg_total,
        "hr_total": hr_total,
        "cn_total": cn_total,
        "cw_total": cw_total,
        "active_days": active_days,
        "total_solved": total_solved,
    }


def build_leaderboard_data(time_range=None):
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
    
    cutoff_date = get_cutoff_date(time_range) if time_range in ("weekly", "monthly") else None

    for user in users:
        name = user.get("name", "Anonymous")
        if not name or name.strip() == "":
            continue
        
        if cutoff_date:
            stats = compute_period_stats(user, cutoff_date, time_range, all_questions=all_questions)
        else:
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
