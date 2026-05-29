"""LeetCode Solved-Status Sync Module.

Fetches a user's accepted LeetCode submissions via the public GraphQL API
and reconciles them with the local DSA tracker ``data.json``.

Design Principles
-----------------
* **Additive-only sync** – existing ``Done: true`` entries are never reverted,
  even if the problem doesn't appear in the remote submission list. This
  preserves any manual progress the user recorded locally.
* **Idempotent** – running the sync twice with the same data produces the same
  result (no duplicate timestamps, no toggled flags).
* **Graceful degradation** – network failures, private profiles, and rate-limit
  responses are caught and reported without crashing the caller.
* **Dual-use** – works both as a standalone CLI script and as an importable
  library for the Flask routes.

Public API
----------
``sync_leetcode_progress(username, data_path)``
    One-call entry point: fetch → match → update → report.
``fetch_accepted_slugs(username)``
    Pure network layer – returns the set of accepted title slugs.
``build_slug_index(data)``
    Builds a reverse index from LeetCode slug → ``(topic_idx, question_idx)``.
``apply_sync(data, slug_index, accepted_slugs)``
    Applies the additive merge and returns a ``SyncReport``.

References
----------
* LeetCode GraphQL endpoint: https://leetcode.com/graphql
* Query: ``recentAcSubmissions`` (public, no auth required for public profiles)
"""

from __future__ import annotations

import json
import logging
import os
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

# Maximum number of recent submissions to request per page.  LeetCode caps
# the ``recentAcSubmissions`` query at 20 per call; we paginate by requesting
# accepted-only submissions until we see no new slugs.
_SUBMISSIONS_PER_PAGE = 20

# Safety cap – stop after this many API pages to avoid runaway loops if the
# API starts returning duplicates indefinitely.
_MAX_PAGES = 50

# HTTP timeout for the GraphQL requests (seconds).
REQUEST_TIMEOUT = 10

# Default path to the local problem database relative to repo root.
DEFAULT_DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")


# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

# ``recentAcSubmissions`` returns the user's accepted submissions without
# authentication.  The ``limit`` argument controls how many items per call
# (max 20).  We use this instead of ``userSubmissionList`` which requires
# an authenticated session.
_RECENT_AC_QUERY = """
query recentAcSubmissions($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) {
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
        LeetCode slugs that had no matching entry in ``data.json``.
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

def _build_recent_ac_payload(username: str, limit: int = _SUBMISSIONS_PER_PAGE) -> dict:
    """Construct the JSON body for the ``recentAcSubmissions`` query."""
    return {
        "query": _RECENT_AC_QUERY,
        "variables": {"username": username, "limit": limit},
    }


def fetch_accepted_slugs(username: str) -> tuple[set[str], list[str]]:
    """Fetch the set of unique accepted title-slugs for *username*.

    Parameters
    ----------
    username : str
        Public LeetCode username (case-insensitive on LeetCode's side).

    Returns
    -------
    accepted : set[str]
        Unique ``titleSlug`` values for accepted submissions.
    errors : list[str]
        Any warning messages generated during fetching.

    Raises
    ------
    No exceptions are raised.  Network and API errors are captured in the
    returned *errors* list so the caller can decide how to surface them.
    """
    accepted: set[str] = set()
    errors: list[str] = []

    headers = {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
    }

    # Paginate through recent accepted submissions.
    # The ``recentAcSubmissionList`` query returns the most recent accepted
    # submissions.  Because LeetCode caps this at 20 per request, we keep
    # calling until the returned list is shorter than the requested limit
    # (indicating we've reached the end) or until we hit our safety cap.
    page = 0
    while page < _MAX_PAGES:
        page += 1
        try:
            response = requests.post(
                LEETCODE_GRAPHQL_URL,
                json=_build_recent_ac_payload(username, _SUBMISSIONS_PER_PAGE),
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

        # GraphQL can return top-level ``errors`` even with a 200 status.
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
            # Empty list means no (more) submissions – stop paginating.
            break

        for sub in submissions:
            slug = sub.get("titleSlug", "").strip()
            if slug:
                accepted.add(slug)

        # The ``recentAcSubmissionList`` endpoint does not support cursor-based
        # pagination – it always returns the same most-recent N items.  So we
        # break after the first successful page.  If LeetCode ever adds offset
        # support, this loop structure is ready for it.
        break

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


def build_slug_index(data: list[dict]) -> dict[str, list[tuple[int, int]]]:
    """Build a mapping from LeetCode slug → list of ``(topic_idx, question_idx)``.

    A single slug can theoretically appear in multiple topics (e.g. the same
    LeetCode problem listed under "Array" and "Searching"), so we store a list.

    Parameters
    ----------
    data : list[dict]
        The parsed ``data.json`` structure – a list of topic objects, each
        containing a ``"questions"`` list.

    Returns
    -------
    dict[str, list[tuple[int, int]]]
        Slug → positions in the ``data`` structure.
    """
    index: dict[str, list[tuple[int, int]]] = {}

    for topic_idx, topic in enumerate(data):
        questions = topic.get("questions", [])
        for q_idx, question in enumerate(questions):
            # Check both "URL" and "url" keys (data.json has mixed casing).
            for url_key in ("URL", "url"):
                slug = extract_leetcode_slug(question.get(url_key, ""))
                if slug:
                    index.setdefault(slug, []).append((topic_idx, q_idx))

    logger.debug("Built slug index with %d LeetCode entries", len(index))
    return index


# ---------------------------------------------------------------------------
# 3. Additive Sync Engine
# ---------------------------------------------------------------------------

def apply_sync(
    data: list[dict],
    slug_index: dict[str, list[tuple[int, int]]],
    accepted_slugs: set[str],
) -> SyncReport:
    """Apply accepted slugs to ``data`` using additive-only merge.

    Rules
    -----
    * If a slug matches a question that is NOT marked ``Done: true``, set it
      to ``true`` → counted as *synced*.
    * If the question is ALREADY ``Done: true``, leave it → counted as
      *already_done*.
    * If a slug has NO match in the index, record it as *skipped_no_match*.
    * Questions that are locally ``Done: true`` but NOT in the accepted set
      are **never** reverted.  This is the core conflict-resolution guarantee.

    Parameters
    ----------
    data : list[dict]
        Mutable reference to the parsed ``data.json``.  Modified in-place.
    slug_index : dict
        Output of ``build_slug_index(data)``.
    accepted_slugs : set[str]
        Output of ``fetch_accepted_slugs()``.

    Returns
    -------
    SyncReport
        Detailed report of the sync operation.
    """
    report = SyncReport()

    for slug in sorted(accepted_slugs):
        positions = slug_index.get(slug)

        if not positions:
            report.skipped_no_match.append(slug)
            continue

        for topic_idx, q_idx in positions:
            question = data[topic_idx]["questions"][q_idx]
            problem_name = question.get("Problem", question.get("problem", slug))

            if question.get("Done", False):
                # Already solved – preserve local state, no mutation.
                report.already_done.append(problem_name)
            else:
                # New solve – flip to Done.
                question["Done"] = True
                report.synced.append(problem_name)

                # Also update the parent topic's bookkeeping counters.
                topic = data[topic_idx]
                topic["doneQuestions"] = topic.get("doneQuestions", 0) + 1
                if not topic.get("started"):
                    topic["started"] = True

    logger.info("Sync complete – %s", report.summary())
    return report


# ---------------------------------------------------------------------------
# 4. File I/O Helpers
# ---------------------------------------------------------------------------

def load_data(path: str) -> list[dict]:
    """Load and parse ``data.json``.

    Parameters
    ----------
    path : str
        Absolute or relative path to ``data.json``.

    Returns
    -------
    list[dict]
        Parsed JSON array of topic objects.

    Raises
    ------
    FileNotFoundError
        If the file doesn't exist.
    json.JSONDecodeError
        If the file contains invalid JSON.
    """
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_data(data: list[dict], path: str) -> None:
    """Write the updated ``data.json`` back to disk.

    Uses a two-step write (write to temp → rename) so that a crash mid-write
    won't corrupt the original file.
    """
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp_path, path)
    logger.info("Saved updated data to %s", path)


# ---------------------------------------------------------------------------
# 5. Top-Level Orchestrator
# ---------------------------------------------------------------------------

def sync_leetcode_progress(
    username: str,
    data_path: str = DEFAULT_DATA_PATH,
    *,
    persist: bool = True,
) -> SyncReport:
    """End-to-end LeetCode sync: fetch → match → update → save.

    This is the primary entry point for both CLI usage and Flask route
    integration.

    Parameters
    ----------
    username : str
        The public LeetCode username to sync.
    data_path : str
        Path to the ``data.json`` file.  Defaults to the repo-root copy.
    persist : bool
        If ``True`` (default), write the updated data back to *data_path*.
        Set to ``False`` for dry-run / preview mode.

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

    # -- Step 2: Load local data and build the slug index --------------------
    try:
        data = load_data(data_path)
    except FileNotFoundError:
        report = SyncReport(errors=[f"data.json not found at {data_path}"])
        return report
    except json.JSONDecodeError as exc:
        report = SyncReport(errors=[f"Invalid JSON in data.json: {exc}"])
        return report

    slug_index = build_slug_index(data)

    # -- Step 3: Apply the additive sync -------------------------------------
    report = apply_sync(data, slug_index, accepted_slugs)

    # Carry over any fetch warnings.
    report.errors.extend(fetch_errors)

    # -- Step 4: Persist if there were actual changes ------------------------
    if persist and report.synced:
        try:
            save_data(data, data_path)
        except OSError as exc:
            report.errors.append(f"Failed to save data.json: {exc}")
            logger.error("Save failed: %s", exc)

    return report


# ---------------------------------------------------------------------------
# 6. CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Command-line interface for standalone usage.

    Usage::

        python leetcode_sync.py <leetcode_username> [path/to/data.json]

    Prints a human-readable sync report to stdout.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python leetcode_sync.py <leetcode_username> [data.json]")
        sys.exit(1)

    username = sys.argv[1]
    data_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DATA_PATH

    print(f"🔄 Syncing LeetCode submissions for '{username}'…")
    report = sync_leetcode_progress(username, data_path)

    # -- Pretty-print the results --------------------------------------------
    if report.synced:
        print(f"\n✅ Newly synced ({len(report.synced)}):")
        for name in report.synced:
            print(f"   • {name}")

    if report.already_done:
        print(f"\n📌 Already solved ({len(report.already_done)}):")
        for name in report.already_done[:10]:
            print(f"   • {name}")
        if len(report.already_done) > 10:
            print(f"   … and {len(report.already_done) - 10} more")

    if report.skipped_no_match:
        print(f"\n⏭️  Not in sheet ({len(report.skipped_no_match)}):")
        for slug in report.skipped_no_match[:10]:
            print(f"   • {slug}")
        if len(report.skipped_no_match) > 10:
            print(f"   … and {len(report.skipped_no_match) - 10} more")

    if report.errors:
        print(f"\n⚠️  Warnings ({len(report.errors)}):")
        for err in report.errors:
            print(f"   • {err}")

    print(f"\n📊 Summary: {report.summary()}")


if __name__ == "__main__":
    main()
