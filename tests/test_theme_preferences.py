import mongomock

import app as app_module
import app.auth.routes as auth_routes
from app.config import TestingConfig


def create_test_app(monkeypatch):
    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app(config_class=TestingConfig)
    flask_app._db_initialized = True

    return flask_app, test_db


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def set_csrf_token(client, token="theme-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def test_theme_preferences_returns_defaults_for_legacy_user(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Theme User",
            "email": "theme@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.get("/theme_preferences")

    assert response.status_code == 200
    assert response.get_json() == {
        "theme_accent": "#ba5912",
        "theme_density": "comfortable",
        "theme_chart_palette": "default",
        "theme_preferences_customized": False,
    }


def test_theme_preferences_can_be_updated(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Theme User",
            "email": "theme@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            "/theme_preferences",
            headers={"X-CSRFToken": csrf_token},
            json={
                "theme_accent": "#2563EB",
                "theme_density": "compact",
                "theme_chart_palette": "colorblind",
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["theme_accent"] == "#2563eb"
    assert payload["theme_preferences_customized"] is True
    user_doc = test_db.user.find_one({"_id": user_id})
    assert user_doc["theme_accent"] == "#2563eb"
    assert user_doc["theme_density"] == "compact"
    assert user_doc["theme_chart_palette"] == "colorblind"
    assert "theme_preferences_updated_at" in user_doc


def test_theme_preferences_update_requires_csrf_token(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Theme User",
            "email": "theme@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.post(
            "/theme_preferences",
            json={
                "theme_accent": "#2563EB",
                "theme_density": "compact",
                "theme_chart_palette": "colorblind",
            },
        )

    assert response.status_code == 403
    assert response.get_json() == {"success": False, "error": "Invalid CSRF token."}


def test_theme_preferences_rejects_invalid_values(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Theme User",
            "email": "theme@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            "/theme_preferences",
            headers={"X-CSRFToken": csrf_token},
            json={
                "theme_accent": "blue",
                "theme_density": "tiny",
                "theme_chart_palette": "unknown",
            },
        )

    assert response.status_code == 400
    errors = response.get_json()["errors"]
    assert set(errors) == {"theme_accent", "theme_density", "theme_chart_palette"}
