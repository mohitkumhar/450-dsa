from bson import ObjectId

import app.auth.routes as auth_routes
import app.profile.routes as profile_routes
import app.tracker.routes as tracker_routes
from app.leaderboard.cache import (
    LEADERBOARD_CACHE_VERSION_KEY,
    api_leaderboard_cache_key,
    cache,
    invalidate_leaderboard_cache,
    leaderboard_page_cache_key,
)
from conftest import build_test_app, csrf_headers


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_leaderboard_cache_keys_change_after_invalidation(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)

    with flask_app.test_request_context("/api/leaderboard?mode=questions&page=1"):
        initial_api_key = api_leaderboard_cache_key()
        invalidate_leaderboard_cache()
        assert cache.get(LEADERBOARD_CACHE_VERSION_KEY) == 1
        assert api_leaderboard_cache_key() != initial_api_key

    with flask_app.test_request_context("/leaderboard"):
        initial_page_key = leaderboard_page_cache_key()
        invalidate_leaderboard_cache()
        assert leaderboard_page_cache_key() != initial_page_key


def test_update_question_invalidates_leaderboard_cache(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    monkeypatch.setattr(auth_routes, "db", test_db)

    calls = []
    monkeypatch.setattr(tracker_routes, "invalidate_leaderboard_cache", lambda: calls.append("invalidated"))

    question_id = test_db.question.insert_one({"topic": ObjectId(), "problem": "Two Sum"}).inserted_id
    user_id = test_db.user.insert_one({"name": "Saurabh", "email": "s@example.com", "progress": {}}).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.post(
            f"/update_question/{question_id}",
            json={"done": True},
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    assert calls == ["invalidated"]


def test_edit_profile_invalidates_leaderboard_cache(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(profile_routes,))
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(profile_routes, "db", test_db)

    calls = []
    monkeypatch.setattr(profile_routes, "invalidate_leaderboard_cache", lambda: calls.append("invalidated"))

    user_id = test_db.user.insert_one({"name": "Saurabh", "email": "s@example.com", "progress": {}}).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.post(
            "/edit_profile",
            json={"name": "Saurabh Kumar Bajpai"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    assert calls == ["invalidated"]
