import mongomock
import werkzeug
from bson import ObjectId

import app as app_module
import app.auth.routes as auth_routes
import app.leaderboard.service as leaderboard_service
import app.profile.routes as profile_routes
import app.utils as utils
import app.web.routes as public_routes


if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"


def create_test_app(monkeypatch):
    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(leaderboard_service, "db", test_db)
    monkeypatch.setattr(profile_routes, "db", test_db)
    monkeypatch.setattr(public_routes, "db", test_db)
    monkeypatch.setattr(utils, "db", test_db)

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app._db_initialized = True
    return flask_app, test_db


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_deactivate_account_marks_user_and_logs_out(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    hashed = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    user_id = test_db.user.insert_one(
        {
            "name": "Deactivate Me",
            "email": "deactivate@example.com",
            "password": hashed,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        with client.session_transaction() as session:
            session["deactivate_csrf_token"] = "deactivate-token"

        response = client.post(
            "/deactivate_account",
            data={"csrf_token": "deactivate-token", "password": "StrongPass1!"},
        )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert user_doc["is_deactivated"] is True
    assert user_doc.get("deactivated_at") is not None


def test_login_reactivates_deactivated_password_user(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    hashed = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    user_id = test_db.user.insert_one(
        {
            "name": "Come Back",
            "email": "reactivate@example.com",
            "password": hashed,
            "progress": {},
            "is_deactivated": True,
            "deactivated_at": "old-value",
        }
    ).inserted_id

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["csrf_token"] = "login-token"
        response = client.post(
            "/login",
            data={
                "email": "reactivate@example.com",
                "password": "StrongPass1!",
                "csrf_token": "login-token",
            },
        )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert user_doc["is_deactivated"] is False
    assert "deactivated_at" not in user_doc


def test_public_profile_and_card_hide_deactivated_user(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Hidden User",
            "email": "hidden@example.com",
            "progress": {},
            "external_totals": {},
            "is_deactivated": True,
        }
    ).inserted_id

    with flask_app.test_client() as client:
        profile_response = client.get(f"/u/{user_id}")
        card_response = client.get(f"/u/{user_id}/card.png")

    assert profile_response.status_code == 404
    assert card_response.status_code == 404


def test_build_leaderboard_data_excludes_deactivated_users(monkeypatch):
    test_db = mongomock.MongoClient().db
    monkeypatch.setattr(leaderboard_service, "db", test_db)

    active_id = test_db.user.insert_one(
        {"_id": ObjectId(), "name": "Active User", "progress": {}, "external_totals": {}}
    ).inserted_id
    test_db.user.insert_one(
        {
            "_id": ObjectId(),
            "name": "Hidden User",
            "progress": {},
            "external_totals": {},
            "is_deactivated": True,
        }
    )

    entries = leaderboard_service.build_leaderboard_data()

    assert [entry["user_id"] for entry in entries] == [str(active_id)]
    assert entries[0]["name"] == "Active User"
