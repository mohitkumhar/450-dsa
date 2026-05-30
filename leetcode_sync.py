"""LeetCode Solved-Status Sync Module.

Fetches a user's accepted LeetCode submissions via the public GraphQL API
and reconciles them with their progress in MongoDB.

Design Principles
-----------------
* **Additive-only sync** – existing progress is never reverted,
  preserving manual progress.
* **Idempotent** – running the sync twice produces the same result.
* **Graceful degradation** – network failures are reported without crashing.
* **Dual-use** – works both as a standalone CLI script and as an importable
  library for the Flask routes.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

# Maximum number of recent submissions to request per page. LeetCode caps
# the query at 20 per call; we paginate using offsets.
_SUBMISSIONS_PER_PAGE = 20

# Safety cap – stop after this many API pages to avoid runaway loops.
_MAX_PAGES = 50

# HTTP timeout for the GraphQL requests (seconds).
REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

_RECENT_AC_QUERY = """
query recentAcSubmissions($username: String!, $limit: Int!, $offset: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit, offset: $offset) {
    titleSlug
    statusDisplay
  }
}
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SyncReport:
    """Summary of a single sync operation.

    Attributes
    ----------
    synced : list[str]
        Problem names that were newly marked as solved.
    already_done : list[str]
        Problem names that were already solved locally.
    skipped_no_match : list[str]
        LeetCode slugs that had no matching entry in MongoDB.
    errors : list[str]
        Free-form error/warning messages encountered during the run.
    """

    synced: list[str] = field(default_factory=list)
    already_done: list[str] = field(default_factory=list)
    skipped_no_match: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # -- convenience helpers --------------------------------------------------

    @property
    def total_fetched(self) -> int:
        """Total number of unique accepted slugs retrieved from LeetCode."""
        return (
            len(self.synced)
            + len(self.already_done)
            + len(self.skipped_no_match)
        )

    def summary(self) -> str:
        """Return a human-readable one-line summary string."""
        parts = [
            f"{len(self.synced)} new problems synced",
            f"{len(self.already_done)} already solved",
            f"{len(self.skipped_no_match)} not in sheet",
        ]
        if self.errors:
            parts.append(f"{len(self.errors)} warnings")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the report for JSON API responses."""
        return {
            "synced": self.synced,
            "synced_count": len(self.synced),
            "already_done_count": len(self.already_done),
            "skipped_no_match": self.skipped_no_match,
            "skipped_no_match_count": len(self.skipped_no_match),
            "errors": self.errors,
            "total_fetched": self.total_fetched,
            "summary": self.summary(),
        }


# ---------------------------------------------------------------------------
# 1. LeetCode GraphQL Fetcher
# ---------------------------------------------------------------------------

def _build_recent_ac_payload(username: str, limit: int = _SUBMISSIONS_PER_PAGE, offset: int = 0) -> dict:
    """Construct the JSON body for the ``recentAcSubmissions`` query."""
    return {
        "query": _RECENT_AC_QUERY,
        "variables": {"username": username, "limit": limit, "offset": offset},
    }


def fetch_accepted_slugs(username: str) -> tuple[set[str], list[str]]:
    """Fetch the set of unique accepted title-slugs for *username*.

    Paginates through submissions using the offset parameter.

    Parameters
    ----------
    username : str
        Public LeetCode username.

    Returns
    -------
    accepted : set[str]
        Unique ``titleSlug`` values for accepted submissions.
    errors : list[str]
        Any warning messages generated during fetching.
    """
    accepted: set[str] = set()
    errors: list[str] = []

    headers = {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
    }

    page = 0
    limit = _SUBMISSIONS_PER_PAGE
    offset = 0

    while page < _MAX_PAGES:
        page += 1
        try:
            response = requests.post(
                LEETCODE_GRAPHQL_URL,
                json=_build_recent_ac_payload(username, limit, offset),
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            errors.append(f"Network error connecting to LeetCode: {exc}")
            logger.error("LeetCode sync connection error: %s", exc)
            break
        except requests.exceptions.Timeout:
            errors.append("LeetCode API request timed out")
            logger.warning("LeetCode sync request timed out")
            break
        except requests.exceptions.RequestException as exc:
            errors.append(f"HTTP request failed: {exc}")
            logger.error("LeetCode sync request error: %s", exc)
            break

        # -- Handle non-200 responses ----------------------------------------
        if response.status_code == 429:
            errors.append("Rate-limited by LeetCode – try again later")
            logger.warning("LeetCode rate limit hit (429)")
            break

        if response.status_code == 403:
            errors.append(
                "LeetCode returned 403 Forbidden – the profile may be private"
            )
            logger.warning("LeetCode 403 – possible private profile")
            break

        if response.status_code != 200:
            errors.append(
                f"Unexpected HTTP {response.status_code} from LeetCode"
            )
            logger.error(
                "LeetCode sync unexpected status %d", response.status_code
            )
            break

        # -- Parse the JSON body ----------------------------------------------
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Failed to decode LeetCode response: {exc}")
            logger.error("LeetCode sync JSON decode error: %s", exc)
            break

        gql_errors = body.get("errors")
        if gql_errors:
            msg = gql_errors[0].get("message", "Unknown GraphQL error")
            errors.append(f"LeetCode API error: {msg}")
            logger.warning("LeetCode GraphQL error: %s", msg)
            break

        submissions = (
            body.get("data", {}).get("recentAcSubmissionList") or []
        )

        if not submissions:
            # Empty list means no more submissions – stop paginating.
            break

        new_slugs_found = False
        for sub in submissions:
            slug = sub.get("titleSlug", "").strip()
            if slug:
                if slug not in accepted:
                    accepted.add(slug)
                    new_slugs_found = True

        # Stop paginating if we received fewer submissions than requested,
        # or if we found no new slugs (meaning we are seeing duplicate pages).
        if len(submissions) < limit or not new_slugs_found:
            break

        offset += limit

    logger.info(
        "Fetched %d unique accepted slugs for '%s'", len(accepted), username
    )
    return accepted, errors


# ---------------------------------------------------------------------------
# 2. Slug Index Builder
# ---------------------------------------------------------------------------

def extract_leetcode_slug(url: str) -> str | None:
    """Extract the LeetCode problem slug from a URL.

    Examples
    --------
    >>> extract_leetcode_slug("https://leetcode.com/problems/two-sum/")
    'two-sum'
    >>> extract_leetcode_slug("https://geeksforgeeks.org/problems/foo/")
    >>> # returns None – not a LeetCode URL
    """
    if not url:
        return None
    try:
        parsed = urlparse(url.strip().lower())
    except Exception:
        return None

    if "leetcode.com" not in (parsed.hostname or ""):
        return None

    # Path typically looks like /problems/<slug>/ or /problems/<slug>/description/
    match = re.match(r"^/problems/([a-z0-9-]+)", parsed.path)
    return match.group(1) if match else None


def build_slug_index(questions: list[dict]) -> dict[str, list[dict]]:
    """Build a mapping from LeetCode slug -> list of question documents.

    A single slug can theoretically appear in multiple questions, so we store a list.

    Parameters
    ----------
    questions : list[dict]
        A list of question documents from MongoDB.

    Returns
    -------
    dict[str, list[dict]]
        Slug -> question documents in MongoDB.
    """
    index: dict[str, list[dict]] = {}

    for question in questions:
        # Check both "URL" and "url" keys.
        for url_key in ("URL", "url"):
            slug = extract_leetcode_slug(question.get(url_key, ""))
            if slug:
                index.setdefault(slug, []).append(question)

    logger.debug("Built slug index with %d LeetCode entries", len(index))
    return index


# ---------------------------------------------------------------------------
# 3. Additive Sync Engine
# ---------------------------------------------------------------------------

def apply_sync(
    user_progress: dict,
    slug_index: dict[str, list[dict]],
    accepted_slugs: set[str],
) -> SyncReport:
    """Apply accepted slugs to user progress using additive-only merge.

    Parameters
    ----------
    user_progress : dict
        Mutable reference to user's existing progress mapping (question_id_str -> progress_dict).
        Modified in-place.
    slug_index : dict
        Output of ``build_slug_index(questions)``.
    accepted_slugs : set[str]
        Output of ``fetch_accepted_slugs()``.

    Returns
    -------
    SyncReport
        Detailed report of the sync operation.
    """
    from app.utils import utc_now
    report = SyncReport()

    for slug in sorted(accepted_slugs):
        questions = slug_index.get(slug)

        if not questions:
            report.skipped_no_match.append(slug)
            continue

        for question in questions:
            q_id = str(question["_id"])
            problem_name = question.get("problem", question.get("Problem", slug))
            existing = user_progress.get(q_id, {})

            if existing.get("done", False):
                # Already solved – preserve local state, no mutation.
                report.already_done.append(problem_name)
            else:
                # New solve – flip to Done.
                user_progress[q_id] = {
                    "done": True,
                    "bookmark": existing.get("bookmark", False),
                    "skipped": False,
                    "notes": existing.get("notes", ""),
                    "timestamp": utc_now()
                }
                report.synced.append(problem_name)

    logger.info("Sync complete – %s", report.summary())
    return report


# ---------------------------------------------------------------------------
# 4. Top-Level Orchestrator
# ---------------------------------------------------------------------------

def sync_leetcode_progress(
    username: str,
    db_handle=None,
    *,
    persist: bool = True,
    user_id=None,
) -> SyncReport:
    """End-to-end LeetCode sync: fetch -> match -> update -> database save.

    This is the primary entry point for both CLI usage and Flask route
    integration.

    Parameters
    ----------
    username : str
        The public LeetCode username to sync.
    db_handle : pymongo.database.Database, optional
        MongoDB database handle. If None, initialized using flask app context.
    persist : bool
        If ``True`` (default), write the updated data back to MongoDB.
        Set to ``False`` for dry-run / preview mode.
    user_id : ObjectId or str, optional
        If provided, lookup user directly by ID. Otherwise, looked up by username.

    Returns
    -------
    SyncReport
        Full report of what was synced, skipped, or errored.
    """
    if not username or not username.strip():
        report = SyncReport()
        report.errors.append("LeetCode username is required")
        return report

    username = username.strip()
    logger.info("Starting LeetCode sync for user '%s'", username)

    # -- Step 1: Fetch accepted slugs from LeetCode --------------------------
    accepted_slugs, fetch_errors = fetch_accepted_slugs(username)

    if fetch_errors and not accepted_slugs:
        # Complete fetch failure – return early with the errors.
        report = SyncReport(errors=fetch_errors)
        return report

    # -- Step 2: Acquire DB handle -------------------------------------------
    if db_handle is None:
        try:
            from app import create_app
            from app.extensions import db as flask_db
            app = create_app()
            with app.app_context():
                return _sync_leetcode_progress_in_context(
                    username, flask_db, accepted_slugs, fetch_errors, persist=persist, user_id=user_id
                )
        except Exception as exc:
            report = SyncReport(errors=[f"Failed to initialize database: {exc}"])
            logger.error("Stand-alone DB init failed: %s", exc)
            return report
    else:
        return _sync_leetcode_progress_in_context(
            username, db_handle, accepted_slugs, fetch_errors, persist=persist, user_id=user_id
        )


def _sync_leetcode_progress_in_context(
    username: str,
    db_handle,
    accepted_slugs: set[str],
    fetch_errors: list[str],
    *,
    persist: bool = True,
    user_id=None,
) -> SyncReport:
    # 1. Retrieve the user document
    if user_id:
        user = db_handle.user.find_one({"_id": user_id})
    else:
        user = db_handle.user.find_one(
            {"leetcode_username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}
        )

    if not user:
        report = SyncReport(errors=[f"User not found for LeetCode username: {username}"])
        return report

    user_id = user["_id"]

    # 2. Retrieve questions and index them
    all_questions = list(db_handle.question.find())
    slug_index = build_slug_index(all_questions)

    # 3. Reconcile user progress
    user_progress = dict(user.get("progress") or {})
    report = apply_sync(user_progress, slug_index, accepted_slugs)
    report.errors.extend(fetch_errors)

    # 4. Save/Persist back to MongoDB
    if persist and report.synced:
        from app.utils import (
            compute_in_sheet_platform_counts,
            update_computed_stats
        )
        from app.leaderboard.cache import invalidate_leaderboard_cache
        from app.profile.card_service import warm_public_card_cache

        solved_items = {q_id: p for q_id, p in user_progress.items() if p.get("done")}
        in_sheet_counts = compute_in_sheet_platform_counts(solved_items, all_questions)

        try:
            # Update user document in database
            db_handle.user.update_one(
                {"_id": user_id},
                {"$set": {
                    "progress": user_progress,
                    "in_sheet_platform_counts": in_sheet_counts
                }}
            )

            # Update computed stats (streaks, progress)
            update_computed_stats(user_id, user_progress, db_handle, len(all_questions))

            # Invalidate caches safely
            try:
                invalidate_leaderboard_cache()
            except Exception as exc:
                logger.warning("Could not invalidate leaderboard cache: %s", exc)

            try:
                warm_public_card_cache(user_id, db_handle=db_handle)
            except Exception as exc:
                logger.warning("Could not warm public card cache: %s", exc)

            logger.info("Saved synced progress to database for user %s", username)
        except Exception as exc:
            report.errors.append(f"Failed to save user progress: {exc}")
            logger.error("DB Save failed: %s", exc)

    return report


# ---------------------------------------------------------------------------
# 5. CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Command-line interface for standalone usage.

    Usage::

        python leetcode_sync.py <leetcode_username>

    Prints a human-readable sync report to stdout.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python leetcode_sync.py <leetcode_username>")
        sys.exit(1)

    username = sys.argv[1]

    print(f"\U0001f504 Syncing LeetCode submissions for '{username}'\u2026")
    report = sync_leetcode_progress(username)

    # -- Pretty-print the results --------------------------------------------
    if report.synced:
        print(f"\n\u2705 Newly synced ({len(report.synced)}):")
        for name in report.synced:
            print(f"   \u2022 {name}")

    if report.already_done:
        print(f"\n\U0001f4cc Already solved ({len(report.already_done)}):")
        for name in report.already_done[:10]:
            print(f"   \u2022 {name}")
        if len(report.already_done) > 10:
            print(f"   \u2026 and {len(report.already_done) - 10} more")

    if report.skipped_no_match:
        print(f"\n\u23ed\ufe0f  Not in sheet ({len(report.skipped_no_match)}):")
        for slug in report.skipped_no_match[:10]:
            print(f"   \u2022 {slug}")
        if len(report.skipped_no_match) > 10:
            print(f"   \u2026 and {len(report.skipped_no_match) - 10} more")

    if report.errors:
        print(f"\n\u26a0\ufe0f  Warnings ({len(report.errors)}):")
        for err in report.errors:
            print(f"   \u2022 {err}")

    print(f"\n\U0001f4ca Summary: {report.summary()}")


if __name__ == "__main__":
    main()
