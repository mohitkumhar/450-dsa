from datetime import datetime, timedelta, timezone

from app.profile.sync_service import build_sync_platforms_response, sync_user_platforms
from app.utils import get_merged_daily_counts


class FakeUser:
    def __init__(self, **kwargs):
        self._doc = kwargs
        self.id = kwargs.get("id", "user-1")
        self.last_sync = kwargs.get("last_sync")
        self.leetcode_username = kwargs.get("leetcode_username", "")
        self.github_username = kwargs.get("github_username", "")
        self.gfg_username = kwargs.get("gfg_username", "")
        self.hackerrank_username = kwargs.get("hackerrank_username", "")
        self.codingninjas_username = kwargs.get("codingninjas_username", "")
        self.atcoder_username = kwargs.get("atcoder_username", "")
        self.platform_calendars = kwargs.get("platform_calendars", {})
        self.external_daily_counts = kwargs.get("external_daily_counts", {})
        self.reload_calls = 0

    @property
    def sync_interval(self):
        return self._doc.get("sync_interval") or "none"

    @property
    def sync_notifications(self):
        val = self._doc.get("sync_notifications")
        return True if val is None else bool(val)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._doc.get(name)

    def reload(self):
        self.reload_calls += 1


class FakeUserCollection:
    def __init__(self):
        self.updates = []

    def update_one(self, query, update):
        self.updates.append((query, update))


class FakeDB:
    def __init__(self):
        self.user = FakeUserCollection()


class FakeCache:
    def __init__(self):
        self.deleted_keys = []

    def delete(self, key):
        self.deleted_keys.append(key)


def test_sync_user_platforms_respects_cooldown():
    now = datetime.now(timezone.utc)
    user = FakeUser(last_sync=now - timedelta(seconds=120))
    db = FakeDB()
    cache = FakeCache()

    payload, status_code = sync_user_platforms(user, {}, db, cache, now=now)

    assert status_code == 200
    assert payload["success"] is False
    assert "Please wait" in payload["error"]
    assert db.user.updates == []
    assert cache.deleted_keys == []
    assert user.reload_calls == 0


def test_sync_user_platforms_updates_totals_and_clears_cache(monkeypatch):
    now = datetime.now(timezone.utc)
    user = FakeUser()
    db = FakeDB()
    cache = FakeCache()

    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode",
        lambda username: {
            "calendar": {"2026-05-24": 3},
            "total": 25,
            "difficulty": {"Easy": 10, "Medium": 12, "Hard": 3},
            "contest": {"attendedContestsCount": 4, "rating": 1725.7, "globalRanking": 3210},
        },
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode_rating_history",
        lambda username: [{"rating": 1700}],
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_lc_badges",
        lambda username: [{"name": "100 Days"}],
    )
    monkeypatch.setattr("app.profile.sync_service.invalidate_leaderboard_cache", lambda: None)

    payload, status_code = sync_user_platforms(
        user,
        {"leetcode": "  alice  "},
        db,
        cache,
        now=now,
    )

    assert status_code == 200
    assert payload["success"] is True
    assert payload["platforms"]["leetcode"]["status"] == "synced"
    assert payload["platforms"]["github"]["status"] == "skipped"

    assert db.user.updates == [
        (
            {"_id": "user-1"},
            {
                "$set": {
                    "last_sync": now,
                    "leetcode_username": "alice",
                    "rating_history": [{"rating": 1700}],
                    "lc_badges_json": '[{"name": "100 Days"}]',
                    "platform_calendars": {"leetcode": {"2026-05-24": 3}},
                    "external_totals": {
                        "LeetCode": 25,
                        "LeetCode_Easy": 10,
                        "LeetCode_Medium": 12,
                        "LeetCode_Hard": 3,
                        "LeetCode_Contests": 4,
                        "LeetCode_Rating": 1725,
                        "LeetCode_GlobalRank": 3210,
                    },
                }
            },
        )
    ]
    assert user.reload_calls == 1


def test_sync_user_platforms_partial_sync_preserves_other_platforms(monkeypatch):
    now = datetime.now(timezone.utc)
    user = FakeUser(platform_calendars={"github": {"2026-05-24": 2}})
    db = FakeDB()
    cache = FakeCache()

    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode",
        lambda username: {
            "calendar": {"2026-05-24": 3, "2026-05-25": 1},
            "total": 10,
            "difficulty": {"Easy": 5, "Medium": 4, "Hard": 1},
            "contest": {"attendedContestsCount": 1, "rating": 1500, "globalRanking": 500},
        },
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode_rating_history",
        lambda username: [],
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_lc_badges",
        lambda username: [],
    )
    monkeypatch.setattr("app.profile.sync_service.invalidate_leaderboard_cache", lambda: None)

    payload, status_code = sync_user_platforms(
        user,
        {"leetcode": "alice"},
        db,
        cache,
        now=now,
    )

    assert status_code == 200
    assert payload["success"] is True

    update_doc = db.user.updates[0][1]
    assert update_doc["$set"]["platform_calendars"] == {
        "github": {"2026-05-24": 2},
        "leetcode": {"2026-05-24": 3, "2026-05-25": 1},
    }


def test_sync_backfills_legacy_external_daily_counts_into_platform_calendars(monkeypatch):
    """On first partial sync after deployment, legacy external_daily_counts are
    backfilled into platform_calendars._legacy so that dates from platforms
    not yet re-synced are preserved. _legacy stays until the user's *other*
    configured platforms (github) are also synced."""
    now = datetime.now(timezone.utc)
    user = FakeUser(
        leetcode_username="alice",
        github_username="octocat",
        external_daily_counts={"2026-05-25": 3, "2026-05-26": 1},
    )
    db = FakeDB()
    cache = FakeCache()

    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode",
        lambda username: {
            "calendar": {"2026-05-25": 2},
            "total": 10,
            "difficulty": {"Easy": 5, "Medium": 4, "Hard": 1},
            "contest": {"attendedContestsCount": 1, "rating": 1500, "globalRanking": 500},
        },
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode_rating_history",
        lambda username: [],
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_lc_badges",
        lambda username: [],
    )
    monkeypatch.setattr("app.profile.sync_service.invalidate_leaderboard_cache", lambda: None)

    payload, status_code = sync_user_platforms(
        user,
        {"leetcode": "alice"},
        db,
        cache,
        now=now,
    )

    assert status_code == 200
    assert payload["success"] is True

    update_doc = db.user.updates[0][1]
    calendars = update_doc["$set"]["platform_calendars"]
    assert "leetcode" in calendars
    assert calendars["leetcode"] == {"2026-05-25": 2}
    assert "_legacy" in calendars
    assert calendars["_legacy"] == {"2026-05-25": 3, "2026-05-26": 1}


def test_sync_removes_legacy_once_all_platforms_synced(monkeypatch):
    """Once every platform the user has configured has been synced into
    platform_calendars, the _legacy entry is removed."""
    now = datetime.now(timezone.utc)
    user = FakeUser(
        leetcode_username="alice",
        external_daily_counts={"2026-05-25": 3},
    )
    db = FakeDB()
    cache = FakeCache()

    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode",
        lambda username: {
            "calendar": {"2026-05-25": 4},
            "total": 10,
            "difficulty": {"Easy": 5, "Medium": 4, "Hard": 1},
            "contest": {"attendedContestsCount": 1, "rating": 1500, "globalRanking": 500},
        },
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_leetcode_rating_history",
        lambda username: [],
    )
    monkeypatch.setattr(
        "app.profile.sync_service.fetch_lc_badges",
        lambda username: [],
    )
    monkeypatch.setattr("app.profile.sync_service.invalidate_leaderboard_cache", lambda: None)

    payload, status_code = sync_user_platforms(
        user,
        {"leetcode": "alice"},
        db,
        cache,
        now=now,
    )

    assert status_code == 200
    assert payload["success"] is True

    update_doc = db.user.updates[0][1]
    calendars = update_doc["$set"]["platform_calendars"]
    assert "leetcode" in calendars
    assert "_legacy" not in calendars


def test_get_merged_daily_counts_uses_max_for_overlapping_legacy_dates():
    """get_merged_daily_counts preserves legacy counts for dates where
    platform_calendars only covers a subset of platforms."""
    user = FakeUser(
        platform_calendars={
            "leetcode": {"2026-05-25": 2},
            "_legacy": {"2026-05-25": 3, "2026-05-26": 1},
        },
    )
    merged = get_merged_daily_counts(user)
    assert merged == {"2026-05-25": 3, "2026-05-26": 1}
    assert merged["2026-05-25"] == 3


def test_get_merged_daily_counts_no_max_for_legacy_after_full_migration():
    """Once _legacy is removed, external_daily_counts is still merged using max()
    so established users don't lose older/higher cumulative history."""
    user = FakeUser(
        platform_calendars={
            "leetcode": {"2026-05-25": 2, "2026-05-26": 1},
            "github": {"2026-05-25": 1, "2026-05-27": 3},
        },
        external_daily_counts={"2026-05-25": 99, "2026-05-28": 5},
    )
    merged = get_merged_daily_counts(user)
    # 2026-05-25: platform sum = 3, legacy = 99 → keep max = 99
    assert merged["2026-05-25"] == 99
    # 2026-05-26, 2026-05-27: from platforms
    assert merged["2026-05-26"] == 1
    assert merged["2026-05-27"] == 3
    # 2026-05-28: missing from platforms, filled from legacy
    assert merged["2026-05-28"] == 5


def test_get_merged_daily_counts_falls_back_to_legacy():
    """When platform_calendars is completely empty (no migration done),
    get_merged_daily_counts falls back to external_daily_counts."""
    user = FakeUser(
        external_daily_counts={"2026-05-25": 3},
    )
    merged = get_merged_daily_counts(user)
    assert merged == {"2026-05-25": 3}


def test_build_sync_platforms_response_all_failed():
    result = build_sync_platforms_response(
        {
            "leetcode": {"status": "failed", "error": "timeout"},
            "github": {"status": "failed", "error": "not found"},
        }
    )
    assert result["success"] is False
    assert "all platforms" in result["error"].lower()


def test_get_users_due_for_auto_sync():
    from app.profile.sync_service import get_users_due_for_auto_sync
    
    now = datetime.now(timezone.utc)
    
    # 1. User not opted in (interval 'none')
    user_none = {"_id": "none", "sync_interval": "none"}
    # 2. Daily user, never attempted
    user_daily_never = {"_id": "daily_never", "sync_interval": "daily"}
    # 3. Daily user, attempted 25 hours ago (due)
    user_daily_due = {"_id": "daily_due", "sync_interval": "daily", "last_auto_sync_attempt": now - timedelta(hours=25)}
    # 4. Daily user, attempted 10 hours ago (not due)
    user_daily_not_due = {"_id": "daily_not_due", "sync_interval": "daily", "last_auto_sync_attempt": now - timedelta(hours=10)}
    # 5. Weekly user, never attempted (due)
    user_weekly_never = {"_id": "weekly_never", "sync_interval": "weekly"}
    # 6. Weekly user, attempted 8 days ago (due)
    user_weekly_due = {"_id": "weekly_due", "sync_interval": "weekly", "last_auto_sync_attempt": now - timedelta(days=8)}
    # 7. Weekly user, attempted 3 days ago (not due)
    user_weekly_not_due = {"_id": "weekly_not_due", "sync_interval": "weekly", "last_auto_sync_attempt": now - timedelta(days=3)}
    
    all_users = [user_none, user_daily_never, user_daily_due, user_daily_not_due, user_weekly_never, user_weekly_due, user_weekly_not_due]
    
    class FakeUserCursor:
        def __init__(self, data):
            self.data = data
        def __iter__(self):
            return iter(self.data)
            
    class FakeDB:
        def __init__(self, data):
            self.user = self
            self.data = data
        def find(self, query):
            # simulate querying daily/weekly
            matching = [u for u in self.data if u.get("sync_interval") in query["sync_interval"]["$in"]]
            return FakeUserCursor(matching)
            
    db = FakeDB(all_users)
    due = get_users_due_for_auto_sync(db, now)
    
    due_ids = [u.id for u in due]
    assert "none" not in due_ids
    assert "daily_never" in due_ids
    assert "daily_due" in due_ids
    assert "daily_not_due" not in due_ids
    assert "weekly_never" in due_ids
    assert "weekly_due" in due_ids
    assert "weekly_not_due" not in due_ids


def test_auto_sync_single_user_no_platforms():
    from app.profile.sync_service import auto_sync_single_user
    
    now = datetime.now(timezone.utc)
    user = FakeUser(id="user-empty")
    db = FakeDB()
    cache = FakeCache()
    
    auto_sync_single_user(user, db, cache, now)
    
    assert db.user.updates == [
        (
            {"_id": "user-empty"},
            {
                "$set": {
                    "last_auto_sync_attempt": now,
                    "last_auto_sync_status": "success",
                    "last_auto_sync_error": None
                }
            }
        )
    ]


def test_auto_sync_single_user_success(monkeypatch):
    from app.profile.sync_service import auto_sync_single_user
    import app.profile.sync_service as profile_sync_service
    
    now = datetime.now(timezone.utc)
    user = FakeUser(id="user-alice", leetcode_username="alice")
    db = FakeDB()
    cache = FakeCache()
    
    monkeypatch.setattr(
        profile_sync_service,
        "sync_user_platforms",
        lambda user, data, db_handle, cache_backend, now: ({"success": True}, 200)
    )
    
    auto_sync_single_user(user, db, cache, now)
    
    assert db.user.updates == [
        (
            {"_id": "user-alice"},
            {
                "$set": {
                    "last_auto_sync_attempt": now,
                    "last_auto_sync_status": "success",
                    "last_auto_sync_error": None
                }
            }
        )
    ]


def test_auto_sync_single_user_failed(monkeypatch):
    from app.profile.sync_service import auto_sync_single_user
    import app.profile.sync_service as profile_sync_service
    
    now = datetime.now(timezone.utc)
    user = FakeUser(id="user-bob", leetcode_username="bob")
    db = FakeDB()
    cache = FakeCache()
    
    monkeypatch.setattr(
        profile_sync_service,
        "sync_user_platforms",
        lambda user, data, db_handle, cache_backend, now: ({"success": False, "error": "API Rate Limit"}, 200)
    )
    
    auto_sync_single_user(user, db, cache, now)
    
    assert db.user.updates == [
        (
            {"_id": "user-bob"},
            {
                "$set": {
                    "last_auto_sync_attempt": now,
                    "last_auto_sync_status": "failed",
                    "last_auto_sync_error": "API Rate Limit"
                }
            }
        )
    ]

