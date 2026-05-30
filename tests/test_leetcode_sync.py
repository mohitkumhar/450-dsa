"""Tests for leetcode_sync module.

Covers:
- GraphQL payload construction with $offset
- Pagination loop behaviour (multi-page, dedup, safety cap)
- Slug extraction and index building from MongoDB question docs
- Additive-only progress merge into user progress dict
- End-to-end sync_leetcode_progress with mocked DB and HTTP
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from leetcode_sync import (
    SyncReport,
    _build_recent_ac_payload,
    apply_sync,
    build_slug_index,
    extract_leetcode_slug,
    fetch_accepted_slugs,
    sync_leetcode_progress,
    _SUBMISSIONS_PER_PAGE,
    _MAX_PAGES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_response(submissions, status_code=200):
    """Build a mock requests.Response for a successful GraphQL call."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "data": {"recentAcSubmissionList": submissions}
    }
    return resp


def _error_response(status_code):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _gql_error_response(message="user not found"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "errors": [{"message": message}],
        "data": None
    }
    return resp


def _make_question(q_id, slug, problem_name=None):
    """Build a minimal MongoDB question document."""
    return {
        "_id": q_id,
        "problem": problem_name or slug.replace("-", " ").title(),
        "url": f"https://leetcode.com/problems/{slug}/",
    }


# ---------------------------------------------------------------------------
# 1. Payload builder
# ---------------------------------------------------------------------------

class TestBuildPayload:
    def test_default_offset_is_zero(self):
        payload = _build_recent_ac_payload("alice")
        assert payload["variables"]["offset"] == 0
        assert payload["variables"]["limit"] == _SUBMISSIONS_PER_PAGE
        assert payload["variables"]["username"] == "alice"

    def test_custom_offset(self):
        payload = _build_recent_ac_payload("bob", limit=10, offset=40)
        assert payload["variables"]["offset"] == 40
        assert payload["variables"]["limit"] == 10

    def test_query_contains_offset_variable(self):
        payload = _build_recent_ac_payload("alice")
        assert "$offset: Int!" in payload["query"]
        assert "offset: $offset" in payload["query"]


# ---------------------------------------------------------------------------
# 2. fetch_accepted_slugs – pagination
# ---------------------------------------------------------------------------

class TestFetchAcceptedSlugs:
    @patch("leetcode_sync.requests.post")
    def test_single_page_under_limit(self, mock_post):
        """When the API returns fewer items than limit, stop after 1 call."""
        subs = [{"titleSlug": "two-sum", "statusDisplay": "Accepted"}]
        mock_post.return_value = _ok_response(subs)

        slugs, errors = fetch_accepted_slugs("alice")

        assert slugs == {"two-sum"}
        assert errors == []
        assert mock_post.call_count == 1

    @patch("leetcode_sync.requests.post")
    def test_multi_page_pagination(self, mock_post):
        """Walks offset 0, 20, 40 and stops when page < limit."""
        page1 = [{"titleSlug": f"p-{i}", "statusDisplay": "Accepted"} for i in range(20)]
        page2 = [{"titleSlug": f"q-{i}", "statusDisplay": "Accepted"} for i in range(20)]
        page3 = [{"titleSlug": f"r-{i}", "statusDisplay": "Accepted"} for i in range(5)]

        mock_post.side_effect = [
            _ok_response(page1),
            _ok_response(page2),
            _ok_response(page3),
        ]

        slugs, errors = fetch_accepted_slugs("alice")

        assert len(slugs) == 45  # 20 + 20 + 5
        assert mock_post.call_count == 3
        assert errors == []

        # Verify offsets were incremented correctly
        calls = mock_post.call_args_list
        assert calls[0].kwargs["json"]["variables"]["offset"] == 0
        assert calls[1].kwargs["json"]["variables"]["offset"] == 20
        assert calls[2].kwargs["json"]["variables"]["offset"] == 40

    @patch("leetcode_sync.requests.post")
    def test_stops_on_empty_page(self, mock_post):
        page1 = [{"titleSlug": f"p-{i}", "statusDisplay": "Accepted"} for i in range(20)]
        mock_post.side_effect = [
            _ok_response(page1),
            _ok_response([]),  # empty
        ]

        slugs, errors = fetch_accepted_slugs("alice")

        assert len(slugs) == 20
        assert mock_post.call_count == 2

    @patch("leetcode_sync.requests.post")
    def test_deduplication_stops_pagination(self, mock_post):
        """If a full page returns only already-seen slugs, stop."""
        page = [{"titleSlug": f"p-{i}", "statusDisplay": "Accepted"} for i in range(20)]
        mock_post.side_effect = [
            _ok_response(page),
            _ok_response(page),  # same slugs → no new_slugs_found
        ]

        slugs, errors = fetch_accepted_slugs("alice")

        assert len(slugs) == 20
        assert mock_post.call_count == 2

    @patch("leetcode_sync.requests.post")
    def test_rate_limit_429(self, mock_post):
        mock_post.return_value = _error_response(429)

        slugs, errors = fetch_accepted_slugs("alice")

        assert slugs == set()
        assert any("Rate-limited" in e for e in errors)

    @patch("leetcode_sync.requests.post")
    def test_private_profile_403(self, mock_post):
        mock_post.return_value = _error_response(403)

        slugs, errors = fetch_accepted_slugs("alice")

        assert slugs == set()
        assert any("403" in e for e in errors)

    @patch("leetcode_sync.requests.post")
    def test_graphql_error(self, mock_post):
        mock_post.return_value = _gql_error_response("user not exist")

        slugs, errors = fetch_accepted_slugs("alice")

        assert slugs == set()
        assert any("user not exist" in e for e in errors)

    @patch("leetcode_sync.requests.post")
    def test_connection_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("DNS fail")

        slugs, errors = fetch_accepted_slugs("alice")

        assert slugs == set()
        assert any("Network error" in e for e in errors)


# ---------------------------------------------------------------------------
# 3. Slug extraction and index
# ---------------------------------------------------------------------------

class TestExtractSlug:
    def test_leetcode_url(self):
        assert extract_leetcode_slug("https://leetcode.com/problems/two-sum/") == "two-sum"

    def test_non_leetcode_url(self):
        assert extract_leetcode_slug("https://geeksforgeeks.org/problems/foo/") is None

    def test_empty(self):
        assert extract_leetcode_slug("") is None
        assert extract_leetcode_slug(None) is None


class TestBuildSlugIndex:
    def test_indexes_by_url_key(self):
        questions = [
            {"_id": "q1", "url": "https://leetcode.com/problems/two-sum/"},
            {"_id": "q2", "URL": "https://leetcode.com/problems/add-two-numbers/"},
            {"_id": "q3", "url": "https://geeksforgeeks.org/problems/foo/"},
        ]
        idx = build_slug_index(questions)

        assert "two-sum" in idx
        assert "add-two-numbers" in idx
        assert "foo" not in idx
        assert len(idx["two-sum"]) == 1
        assert idx["two-sum"][0]["_id"] == "q1"

    def test_duplicate_slug_multiple_questions(self):
        questions = [
            {"_id": "q1", "url": "https://leetcode.com/problems/two-sum/"},
            {"_id": "q2", "url": "https://leetcode.com/problems/two-sum/"},
        ]
        idx = build_slug_index(questions)
        assert len(idx["two-sum"]) == 2


# ---------------------------------------------------------------------------
# 4. apply_sync – additive merge on user progress dict
# ---------------------------------------------------------------------------

class TestApplySync:
    @patch("leetcode_sync.apply_sync.__module__", "leetcode_sync")
    def test_new_problem_marked_done(self, monkeypatch):
        monkeypatch.setattr("app.utils.utc_now", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        questions = [_make_question("q1", "two-sum")]
        slug_index = build_slug_index(questions)
        user_progress = {}

        report = apply_sync(user_progress, slug_index, {"two-sum"})

        assert "Two Sum" in report.synced
        assert user_progress["q1"]["done"] is True
        assert user_progress["q1"]["skipped"] is False

    def test_already_done_not_overwritten(self, monkeypatch):
        monkeypatch.setattr("app.utils.utc_now", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        questions = [_make_question("q1", "two-sum")]
        slug_index = build_slug_index(questions)
        user_progress = {"q1": {"done": True, "notes": "my notes"}}

        report = apply_sync(user_progress, slug_index, {"two-sum"})

        assert len(report.already_done) == 1
        assert len(report.synced) == 0
        # Original notes preserved
        assert user_progress["q1"]["notes"] == "my notes"

    def test_unmatched_slug_skipped(self, monkeypatch):
        monkeypatch.setattr("app.utils.utc_now", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        slug_index = build_slug_index([])
        user_progress = {}

        report = apply_sync(user_progress, slug_index, {"unknown-problem"})

        assert "unknown-problem" in report.skipped_no_match
        assert len(report.synced) == 0

    def test_preserves_existing_bookmark(self, monkeypatch):
        monkeypatch.setattr("app.utils.utc_now", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        questions = [_make_question("q1", "two-sum")]
        slug_index = build_slug_index(questions)
        user_progress = {"q1": {"done": False, "bookmark": True, "notes": "review later"}}

        report = apply_sync(user_progress, slug_index, {"two-sum"})

        assert user_progress["q1"]["done"] is True
        assert user_progress["q1"]["bookmark"] is True
        assert user_progress["q1"]["notes"] == "review later"


# ---------------------------------------------------------------------------
# 5. sync_leetcode_progress – end-to-end with mocked DB
# ---------------------------------------------------------------------------

class TestSyncLeetcodeProgress:
    def test_empty_username_returns_error(self):
        report = sync_leetcode_progress("", db_handle=MagicMock())
        assert any("required" in e.lower() for e in report.errors)

    @patch("leetcode_sync.fetch_accepted_slugs")
    def test_complete_fetch_failure_returns_errors(self, mock_fetch):
        mock_fetch.return_value = (set(), ["Network error"])

        report = sync_leetcode_progress("alice", db_handle=MagicMock())

        assert any("Network error" in e for e in report.errors)
        assert report.total_fetched == 0

    @patch("leetcode_sync.fetch_accepted_slugs")
    def test_user_not_found_returns_error(self, mock_fetch):
        mock_fetch.return_value = ({"two-sum"}, [])

        db = MagicMock()
        db.user.find_one.return_value = None

        report = sync_leetcode_progress("alice", db_handle=db, user_id="uid1")

        assert any("not found" in e.lower() for e in report.errors)

    @patch("leetcode_sync.fetch_accepted_slugs")
    def test_syncs_new_problems_to_mongodb(self, mock_fetch, monkeypatch):
        monkeypatch.setattr("app.utils.utc_now", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        mock_fetch.return_value = ({"two-sum"}, [])

        db = MagicMock()
        db.user.find_one.return_value = {
            "_id": "uid1",
            "progress": {},
        }
        db.question.find.return_value = [
            _make_question("q1", "two-sum"),
        ]

        # Mock the imported helpers
        monkeypatch.setattr(
            "app.utils.compute_in_sheet_platform_counts",
            lambda solved, qs: {"LeetCode": 1},
        )
        monkeypatch.setattr(
            "app.utils.update_computed_stats",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "app.leaderboard.cache.invalidate_leaderboard_cache",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.profile.card_service.warm_public_card_cache",
            lambda *a, **kw: None,
        )

        report = sync_leetcode_progress("alice", db_handle=db, user_id="uid1")

        assert "Two Sum" in report.synced
        assert report.errors == []

        # Verify MongoDB was updated
        db.user.update_one.assert_called_once()
        call_args = db.user.update_one.call_args
        assert call_args[0][0] == {"_id": "uid1"}
        set_doc = call_args[0][1]["$set"]
        assert set_doc["progress"]["q1"]["done"] is True
        assert set_doc["in_sheet_platform_counts"] == {"LeetCode": 1}

    @patch("leetcode_sync.fetch_accepted_slugs")
    def test_dry_run_does_not_write(self, mock_fetch, monkeypatch):
        monkeypatch.setattr("app.utils.utc_now", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        mock_fetch.return_value = ({"two-sum"}, [])

        db = MagicMock()
        db.user.find_one.return_value = {
            "_id": "uid1",
            "progress": {},
        }
        db.question.find.return_value = [
            _make_question("q1", "two-sum"),
        ]

        report = sync_leetcode_progress("alice", db_handle=db, user_id="uid1", persist=False)

        assert "Two Sum" in report.synced
        db.user.update_one.assert_not_called()


# ---------------------------------------------------------------------------
# 6. SyncReport
# ---------------------------------------------------------------------------

class TestSyncReport:
    def test_summary_format(self):
        report = SyncReport(
            synced=["A", "B"],
            already_done=["C"],
            skipped_no_match=["D"],
        )
        s = report.summary()
        assert "2 new problems synced" in s
        assert "1 already solved" in s

    def test_to_dict_keys(self):
        report = SyncReport()
        d = report.to_dict()
        assert "synced" in d
        assert "synced_count" in d
        assert "total_fetched" in d
