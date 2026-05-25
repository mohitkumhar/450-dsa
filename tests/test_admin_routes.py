from datetime import datetime, timezone

import mongomock
from bson import ObjectId

import app as app_module
import app.admin.routes as admin_routes
import app.auth.routes as auth_routes


def create_test_app(monkeypatch):
    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(admin_routes, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)

    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True

    return flask_app, test_db


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def set_csrf_token(client, token="test-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def test_admin_dashboard_redirects_when_not_logged_in(monkeypatch):
    flask_app, _ = create_test_app(monkeypatch)

    with flask_app.test_client() as client:
        response = client.get("/admin")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_non_admin_gets_403_for_admin_dashboard(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Normal User",
            "email": "normal@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.get("/admin")

    assert response.status_code == 403


def test_admin_dashboard_supports_search_and_pagination(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Admin",
            "email": "admin@example.com",
            "is_admin": True,
            "progress": {},
            "external_daily_counts": {datetime.now(timezone.utc).strftime("%Y-%m-%d"): 1},
        }
    ).inserted_id

    for index in range(15):
        test_db.user.insert_one(
            {
                "name": f"User {index}",
                "email": f"user{index}@example.com",
                "is_admin": False,
                "progress": {},
            }
        )

    test_db.user.insert_one(
        {
            "name": "Target Search",
            "email": "target@example.com",
            "is_admin": False,
            "progress": {},
        }
    )

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        response = client.get("/admin?q=target&page=1")

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Target Search" in body
    assert "Page 1 of 1" in body


def test_admin_cannot_delete_self(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Self Admin",
            "email": "self@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            f"/admin/users/{admin_id}/delete",
            data={"q": "", "page": 1, "csrf_token": csrf_token},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert test_db.user.find_one({"_id": ObjectId(str(admin_id))}) is not None
    assert "You cannot delete your own account." in response.data.decode("utf-8")


def test_admin_can_delete_other_user(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Main Admin",
            "email": "admin@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id
    victim_id = test_db.user.insert_one(
        {
            "name": "Spam Bot",
            "email": "bot@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            f"/admin/users/{victim_id}/delete",
            data={"q": "", "page": 1, "csrf_token": csrf_token},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert test_db.user.find_one({"_id": victim_id}) is None
    assert "Deleted account for Spam Bot." in response.data.decode("utf-8")
    audit_entry = test_db.admin_audit_log.find_one({"action": "delete_user"})
    assert audit_entry is not None
    assert audit_entry["target_user_id"] == victim_id


def test_admin_delete_rejects_missing_csrf(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Main Admin",
            "email": "admin@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id
    victim_id = test_db.user.insert_one(
        {
            "name": "Victim",
            "email": "victim@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        set_csrf_token(client)
        response = client.post(f"/admin/users/{victim_id}/delete", data={"q": "", "page": 1})

    assert response.status_code == 400
    assert test_db.user.find_one({"_id": victim_id}) is not None


def test_non_admin_cannot_delete_users(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Basic",
            "email": "basic@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id
    victim_id = test_db.user.insert_one(
        {
            "name": "Victim",
            "email": "victim@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.post(f"/admin/users/{victim_id}/delete", data={"q": "", "page": 1})

    assert response.status_code == 403
    assert test_db.user.find_one({"_id": victim_id}) is not None


def test_admin_can_promote_other_user(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Lead Admin",
            "email": "lead@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id
    member_id = test_db.user.insert_one(
        {
            "name": "Member",
            "email": "member@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            f"/admin/users/{member_id}/role",
            data={"q": "", "page": 1, "csrf_token": csrf_token, "make_admin": "1"},
            follow_redirects=True,
        )

    promoted_user = test_db.user.find_one({"_id": member_id})
    assert response.status_code == 200
    assert promoted_user["is_admin"] is True
    assert "Promoted Member to admin." in response.data.decode("utf-8")
    audit_entry = test_db.admin_audit_log.find_one({"action": "promote_admin"})
    assert audit_entry is not None
    assert audit_entry["target_user_id"] == member_id


def test_admin_can_demote_other_admin(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Lead Admin",
            "email": "lead@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id
    target_admin_id = test_db.user.insert_one(
        {
            "name": "Second Admin",
            "email": "second@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            f"/admin/users/{target_admin_id}/role",
            data={"q": "", "page": 1, "csrf_token": csrf_token, "make_admin": "0"},
            follow_redirects=True,
        )

    demoted_user = test_db.user.find_one({"_id": target_admin_id})
    assert response.status_code == 200
    assert demoted_user["is_admin"] is False
    assert "Demoted Second Admin to user." in response.data.decode("utf-8")
    audit_entry = test_db.admin_audit_log.find_one({"action": "demote_admin"})
    assert audit_entry is not None
    assert audit_entry["target_user_id"] == target_admin_id


def test_admin_cannot_demote_self(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Solo Admin",
            "email": "solo@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        response = client.post(
            f"/admin/users/{admin_id}/role",
            data={"q": "", "page": 1, "csrf_token": csrf_token, "make_admin": "0"},
            follow_redirects=True,
        )

    user_doc = test_db.user.find_one({"_id": admin_id})
    assert response.status_code == 200
    assert user_doc["is_admin"] is True
    assert "You cannot remove your own admin access." in response.data.decode("utf-8")


def test_admin_role_change_rejects_missing_csrf(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {
            "name": "Lead Admin",
            "email": "lead@example.com",
            "is_admin": True,
            "progress": {},
        }
    ).inserted_id
    member_id = test_db.user.insert_one(
        {
            "name": "Member",
            "email": "member@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        set_csrf_token(client)
        response = client.post(
            f"/admin/users/{member_id}/role",
            data={"q": "", "page": 1, "make_admin": "1"},
        )

    member = test_db.user.find_one({"_id": member_id})
    assert response.status_code == 400
    assert member["is_admin"] is False


def test_non_admin_cannot_change_roles(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Basic",
            "email": "basic@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id
    target_id = test_db.user.insert_one(
        {
            "name": "Target",
            "email": "target@example.com",
            "is_admin": False,
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.post(
            f"/admin/users/{target_id}/role",
            data={"q": "", "page": 1, "make_admin": "1"},
        )

    target_user = test_db.user.find_one({"_id": target_id})
    assert response.status_code == 403
    assert target_user["is_admin"] is False
