from bson import ObjectId

from conftest import build_test_app, login_test_user
from app.leaderboard.service import (
    LEADERBOARD_SNAPSHOT_CACHE_KEY,
    build_leaderboard_snapshots,
    clear_leaderboard_snapshots,
    get_leaderboard_snapshot,
    refresh_leaderboard_snapshots,
)
from app.leaderboard import service as leaderboard_service
import app.profile.routes as profile_routes
import app.tracker.routes as tracker_routes


class FakeCache:
    def __init__(self):
        self.values = {}
        self.set_calls = []
        self.delete_calls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, timeout=None):
        self.values[key] = value
        self.set_calls.append((key, timeout))

    def delete(self, key):
        self.values.pop(key, None)
        self.delete_calls.append(key)


def test_get_leaderboard_snapshot_uses_cached_snapshots(monkeypatch):
    fake_cache = FakeCache()
    build_calls = []

    monkeypatch.setattr(leaderboard_service, "cache", fake_cache)
    monkeypatch.setattr(
        leaderboard_service,
        "build_leaderboard_snapshots",
        lambda: build_calls.append("built") or {
            "cscore": [{"user_id": "1", "rank": 1, "c_score": 42}],
            "questions": [{"user_id": "1", "rank": 1, "total_solved": 10}],
            "rating": [{"user_id": "1", "rank": 1, "lc_rating": 1800}],
            "college": [{"user_id": "", "rank": 1, "college": "Alpha"}],
        },
    )

    first = get_leaderboard_snapshot("cscore")
    second = get_leaderboard_snapshot("questions")

    assert build_calls == ["built"]
    assert fake_cache.set_calls == [(LEADERBOARD_SNAPSHOT_CACHE_KEY, leaderboard_service.LEADERBOARD_SNAPSHOT_TTL)]
    assert first[0]["c_score"] == 42
    assert second[0]["total_solved"] == 10


def test_refresh_and_clear_leaderboard_snapshots(monkeypatch):
    fake_cache = FakeCache()

    monkeypatch.setattr(leaderboard_service, "cache", fake_cache)
    monkeypatch.setattr(
        leaderboard_service,
        "build_leaderboard_snapshots",
        lambda: {
            "cscore": [{"rank": 1}],
            "questions": [{"rank": 1}],
            "rating": [{"rank": 1}],
            "college": [{"rank": 1}],
        },
    )

    snapshots = refresh_leaderboard_snapshots()
    clear_leaderboard_snapshots()

    assert snapshots["cscore"][0]["rank"] == 1
    assert fake_cache.delete_calls == [LEADERBOARD_SNAPSHOT_CACHE_KEY]


def test_build_leaderboard_snapshots_assigns_ranks(monkeypatch):
    monkeypatch.setattr(
        leaderboard_service,
        "build_leaderboard_data",
        lambda: [
            {
                "user_id": "1",
                "name": "Alice",
                "college": "Alpha",
                "profile_photo": "",
                "c_score": 20,
                "total_solved": 15,
                "dsa_done": 8,
                "lc_total": 10,
                "gfg_total": 2,
                "cn_total": 1,
                "hr_total": 0,
                "lc_rating": 1500,
            },
            {
                "user_id": "2",
                "name": "Bob",
                "college": "Beta",
                "profile_photo": "",
                "c_score": 30,
                "total_solved": 12,
                "dsa_done": 7,
                "lc_total": 9,
                "gfg_total": 1,
                "cn_total": 0,
                "hr_total": 0,
                "lc_rating": 1700,
            },
        ],
    )

    snapshots = build_leaderboard_snapshots()

    assert snapshots["cscore"][0]["user_id"] == "2"
    assert snapshots["cscore"][0]["rank"] == 1
    assert snapshots["questions"][0]["user_id"] == "1"
    assert snapshots["rating"][0]["user_id"] == "2"
    assert snapshots["college"][0]["rank"] == 1


def test_update_question_invalidates_leaderboard_snapshots(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id
    invalidations = []

    monkeypatch.setattr(tracker_routes, "clear_leaderboard_snapshots", lambda: invalidations.append("cleared"))

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json={"done": True})

    assert response.status_code == 200
    assert invalidations == ["cleared"]


def test_edit_profile_invalidates_leaderboard_snapshots(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(profile_routes,))
    invalidations = []

    monkeypatch.setattr(profile_routes, "clear_leaderboard_snapshots", lambda: invalidations.append("cleared"))

    with flask_app.test_client() as client:
        user_id = test_db.user.insert_one(
            {"email": "user@example.com", "progress": {}, "is_admin": False, "name": "Before"}
        ).inserted_id
        login_test_user(client, user_id)
        response = client.post("/edit_profile", json={"name": "After", "college": "New College"})

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert invalidations == ["cleared"]
