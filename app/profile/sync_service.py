import json
import logging

from app.leaderboard.cache import invalidate_leaderboard_cache
from app.platforms.fetchers import (
    fetch_atcoder,
    fetch_coding_ninjas,
    fetch_codewars,
    fetch_gfg,
    fetch_github,
    fetch_hr_badges,
    fetch_lc_badges,
    fetch_leetcode,
    fetch_leetcode_rating_history,
    run_fetch_jobs,
)
from app.utils import ensure_utc_datetime, normalize_coding_ninjas_profile_id, utc_now
from profile_validation import validate_username

logger = logging.getLogger("flask.app")


SYNC_COOLDOWN_SECONDS = 600

PLATFORM_KEYS = {"leetcode", "github", "gfg", "hackerrank",
                 "codingninjas", "atcoder", "codewars"}

PLATFORM_TOTAL_KEYS = {
    "leetcode": {"LeetCode", "LeetCode_Easy", "LeetCode_Medium", "LeetCode_Hard",
                 "LeetCode_Contests", "LeetCode_Rating", "LeetCode_GlobalRank"},
    "github": {"GitHub_Issues", "GitHub_PRs", "GitHub_Merged_PRs", "GitHub_Commits"},
    "gfg": {"GFG"},
    "codingninjas": {"Coding Ninjas"},
    "hackerrank": {"HackerRank"},
    "atcoder": {"AtCoder"},
    "codewars": {"Codewars"},
}


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


def clear_profile_caches(cache_backend, user_id):
    from app.profile.card_service import delete_card_cache
    delete_card_cache(str(user_id))


def build_platform_sync_jobs(
    leetcode_username="",
    github_username="",
    gfg_username="",
    codingninjas_username="",
    hackerrank_username="",
    atcoder_username="",
    codewars_username="",
):
    jobs = {}

    if leetcode_username:

        def fetch_leetcode_bundle():
            result = {"stats": fetch_leetcode(leetcode_username)}
            try:
                rating_history = fetch_leetcode_rating_history(leetcode_username)
                if rating_history:
                    result["rating_history"] = rating_history
            except Exception as exc:
                logger.warning(f"LeetCode rating history sync failed: {exc}")
            try:
                result["badges"] = fetch_lc_badges(leetcode_username)
            except Exception as exc:
                logger.warning(f"LeetCode badges sync failed: {exc}")
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

    if codewars_username:
        jobs["codewars"] = lambda: fetch_codewars(codewars_username)

    return jobs


def sync_user_platforms(user, data, db_handle, cache_backend, now=None):
    now = now or utc_now()
    user_id = user.id

    last_sync = user.last_sync
    if last_sync:
        last_sync = ensure_utc_datetime(last_sync)
        diff = (now - last_sync).total_seconds()
        if diff < SYNC_COOLDOWN_SECONDS:
            remaining = int(SYNC_COOLDOWN_SECONDS - diff)
            mins = remaining // 60
            secs = remaining % 60
            return {
                "success": False,
                "error": f"Please wait {mins}m {secs}s before syncing again.",
            }, 200

    update_fields = {"last_sync": now}

    leetcode_username = user.leetcode_username or ""
    github_username = user.github_username or ""
    gfg_username = user.gfg_username or ""
    hackerrank_username = user.hackerrank_username or ""
    codingninjas_username = user.codingninjas_username or ""
    atcoder_username = user.atcoder_username or ""
    codewars_username = getattr(user, "codewars_username", "") or ""

    try:
        if "leetcode" in data:
            leetcode_username = data.get("leetcode", "").strip()
            update_fields["leetcode_username"] = validate_username(leetcode_username)
        if "github" in data:
            github_username = data.get("github", "").strip()
            update_fields["github_username"] = validate_username(github_username)
        if "gfg" in data:
            gfg_username = data.get("gfg", "").strip()
            update_fields["gfg_username"] = validate_username(gfg_username)
        if "hackerrank" in data:
            hackerrank_username = data.get("hackerrank", "").strip()
            update_fields["hackerrank_username"] = validate_username(hackerrank_username)
        if "codingninjas" in data:
            codingninjas_username = normalize_coding_ninjas_profile_id(data.get("codingninjas", ""))
            update_fields["codingninjas_username"] = validate_username(codingninjas_username)
        if "atcoder" in data:
            atcoder_username = data.get("atcoder", "").strip()
            update_fields["atcoder_username"] = validate_username(atcoder_username)
        if "codewars" in data:
            codewars_username = data.get("codewars", "").strip()
            update_fields["codewars_username"] = validate_username(codewars_username)
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400

    existing_totals = getattr(user, "external_totals", {}) or {}
    if not isinstance(existing_totals, dict):
        existing_totals = {}
    platform_totals = dict(existing_totals)

    # Clear totals for platforms included in this sync so stale data
    # does not persist when a sync fails or a username is cleared.
    for platform_key in data:
        if platform_key in PLATFORM_TOTAL_KEYS:
            for total_key in PLATFORM_TOTAL_KEYS[platform_key]:
                platform_totals.pop(total_key, None)

    platform_status = {}

    def _mark(platform_key: str, status: str, error: str = None):
        payload = {"status": status}
        if error:
            payload["error"] = error
        platform_status[platform_key] = payload

    # Preserve existing per-platform calendar data across partial syncs
    existing_calendars = getattr(user, "platform_calendars", {})
    if not isinstance(existing_calendars, dict):
        existing_calendars = {}
    platform_calendars = dict(existing_calendars)

    platform_jobs = build_platform_sync_jobs(
        leetcode_username=leetcode_username,
        github_username=github_username,
        gfg_username=gfg_username,
        codingninjas_username=codingninjas_username,
        hackerrank_username=hackerrank_username,
        atcoder_username=atcoder_username,
        codewars_username=codewars_username,
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
            platform_calendars["leetcode"] = leetcode_data.get("calendar", {})
            if leetcode_data.get("total") is not None:
                platform_totals["LeetCode"] = leetcode_data.get("total")
            if leetcode_data.get("difficulty"):
                platform_totals["LeetCode_Easy"] = leetcode_data["difficulty"].get("Easy", 0)
                platform_totals["LeetCode_Medium"] = leetcode_data["difficulty"].get("Medium", 0)
                platform_totals["LeetCode_Hard"] = leetcode_data["difficulty"].get("Hard", 0)
            if leetcode_data.get("contest"):
                platform_totals["LeetCode_Contests"] = leetcode_data["contest"].get(
                    "attendedContestsCount", 0
                )
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
            platform_calendars["github"] = github_data.get("calendar", {})
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
            gfg_total = gfg_data.get("total")
            if gfg_total is not None and int(gfg_total) > 0:
                platform_totals["GFG"] = int(gfg_total)
                _mark("gfg", "synced")
            else:
                _mark("gfg", "failed", "No solved problems found (username may be invalid).")
    else:
        _mark("gfg", "skipped")

    if codingninjas_username:
        codingninjas_data = platform_results.get("codingninjas")
        if platform_errors.get("codingninjas"):
            _mark("codingninjas", "failed", "Failed to fetch Coding Ninjas stats.")
        elif not codingninjas_data:
            _mark("codingninjas", "failed", "No data returned (username may be invalid or rate-limited).")
        else:
            cn_total = codingninjas_data.get("total")
            if cn_total is not None and int(cn_total) > 0:
                platform_totals["Coding Ninjas"] = int(cn_total)
                _mark("codingninjas", "synced")
            else:
                _mark("codingninjas", "failed", "No solved problems found (username may be invalid).")
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
                _mark("hackerrank", "failed", "No solved problems found (username may be invalid).")
    else:
        _mark("hackerrank", "skipped")

    if atcoder_username:
        atcoder_data = platform_results.get("atcoder")
        if platform_errors.get("atcoder"):
            _mark("atcoder", "failed", "Failed to fetch AtCoder stats.")
        elif not atcoder_data:
            _mark("atcoder", "failed", "No data returned (handle may be invalid or rate-limited).")
        else:
            atcoder_total = atcoder_data.get("total")
            if atcoder_total is not None and int(atcoder_total) > 0:
                platform_totals["AtCoder"] = int(atcoder_total)
                _mark("atcoder", "synced")
            else:
                _mark("atcoder", "failed", "No solved problems found (handle may be invalid).")
    else:
        _mark("atcoder", "skipped")

    if codewars_username:
        codewars_data = platform_results.get("codewars")
        if platform_errors.get("codewars"):
            _mark("codewars", "failed", "Failed to fetch Codewars stats.")
        elif not codewars_data:
            _mark("codewars", "failed", "No data returned (username may be invalid or rate-limited).")
        else:
            cw_total = codewars_data.get("total")
            if cw_total is not None and int(cw_total) > 0:
                platform_totals["Codewars"] = int(cw_total)
                _mark("codewars", "synced")
            else:
                _mark("codewars", "failed", "No solved problems found (username may be invalid).")
    else:
        _mark("codewars", "skipped")

    # Backfill or remove ``_legacy`` depending on whether the current sync
    # covered every platform the user has configured.  During the migration
    # from the old flat ``external_daily_counts`` format to per-platform
    # calendars, ``_legacy`` preserves dates from platforms not yet re-synced.
    requested_platforms = {k for k in data if k in PLATFORM_KEYS}
    legacy_counts = getattr(user, "external_daily_counts", {})
    has_legacy = isinstance(legacy_counts, dict) and bool(legacy_counts)

    if has_legacy:
        user_platforms = set()
        for attr in ("leetcode_username", "github_username", "gfg_username",
                     "hackerrank_username", "codingninjas_username",
                     "atcoder_username", "codewars_username"):
            if getattr(user, attr, ""):
                platform_name = attr.replace("_username", "")
                user_platforms.add(platform_name)

        if user_platforms and requested_platforms and user_platforms.issubset(requested_platforms):
            # All user platforms were included in this sync → migration done
            platform_calendars.pop("_legacy", None)
        else:
            # Partial sync — preserve legacy data for platforms not yet re-synced
            platform_calendars["_legacy"] = dict(legacy_counts)

    update_fields["platform_calendars"] = platform_calendars
    update_fields["external_totals"] = platform_totals
    db_handle.user.update_one({"_id": user_id}, {"$set": update_fields})
    user.reload()

    invalidate_leaderboard_cache()
    clear_profile_caches(cache_backend, user_id)
    return build_sync_platforms_response(platform_status), 200
