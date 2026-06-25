from bson import ObjectId

import app.auth.routes as auth_routes
import app.tracker.routes as tracker_routes
from conftest import build_test_app, login_test_user


def test_json_post_rejects_missing_csrf_token(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json={"done": True})

    assert response.status_code == 403
    assert response.get_json() == {"success": False, "error": "Invalid CSRF token."}
    user_doc = test_db.user.find_one({"_id": ObjectId(str(user_id))})
    assert user_doc["progress"] == {}


def test_delete_account_accepts_one_time_delete_csrf_token(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {"email": "oauth@example.com", "progress": {}, "is_admin": False}
    ).inserted_id

    invalidated = {"leaderboard": 0, "profile": 0}
    monkeypatch.setattr(auth_routes, "invalidate_leaderboard_cache", lambda: invalidated.__setitem__("leaderboard", invalidated["leaderboard"] + 1))
    monkeypatch.setattr(auth_routes, "clear_profile_caches", lambda _cache, _user_id: invalidated.__setitem__("profile", invalidated["profile"] + 1))

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        with client.session_transaction() as session:
            session["delete_csrf_token"] = "delete-token"

        response = client.post("/delete_account", data={"csrf_token": "delete-token"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert test_db.user.find_one({"_id": user_id}) is None
    assert invalidated["leaderboard"] == 1
    assert invalidated["profile"] == 1


def test_delete_account_rejects_missing_csrf_token(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {"email": "oauth@example.com", "progress": {}, "is_admin": False}
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post("/delete_account")

    assert response.status_code == 403
    assert test_db.user.find_one({"_id": user_id}) is not None
