from datetime import datetime, timedelta, timezone

from app.profile.sync_service import build_sync_platforms_response, sync_user_platforms


class FakeUser:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "user-1")
        self.last_sync = kwargs.get("last_sync")
        self.leetcode_username = kwargs.get("leetcode_username", "")
        self.github_username = kwargs.get("github_username", "")
        self.gfg_username = kwargs.get("gfg_username", "")
        self.hackerrank_username = kwargs.get("hackerrank_username", "")
        self.codingninjas_username = kwargs.get("codingninjas_username", "")
        self.atcoder_username = kwargs.get("atcoder_username", "")
        self.reload_calls = 0

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
                    "external_daily_counts": {"2026-05-24": 3},
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
    assert cache.deleted_keys == ["card_user-1"]
    assert user.reload_calls == 1


def test_build_sync_platforms_response_all_failed():
    result = build_sync_platforms_response(
        {
            "leetcode": {"status": "failed", "error": "timeout"},
            "github": {"status": "failed", "error": "not found"},
        }
    )
    assert result["success"] is False
    assert "all platforms" in result["error"].lower()
