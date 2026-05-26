import io
import json
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


def test_admin_can_preview_and_import_json_sheet(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {"name": "Admin", "email": "admin@example.com", "is_admin": True, "progress": {}}
    ).inserted_id

    payload = [
        {
            "topicName": "Graphs",
            "position": 9,
            "questions": [
                {
                    "Problem": "Clone Graph",
                    "URL": "https://leetcode.com/problems/clone-graph/",
                    "URL2": "",
                    "difficulty": "Medium",
                    "position": 0,
                }
            ],
        }
    ]

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        preview_response = client.post(
            "/admin/import-sheet",
            data={
                "sheet_file": (io.BytesIO(json.dumps(payload).encode("utf-8")), "custom-sheet.json"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        csrf_token = set_csrf_token(client)
        import_response = client.post(
            "/admin/import-sheet/confirm",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )

    assert preview_response.status_code == 200
    preview_body = preview_response.data.decode("utf-8")
    assert "Clone Graph" in preview_body
    assert "Import Sheet" in preview_body
    assert import_response.status_code == 200
    assert test_db.topic.find_one({"name": "Graphs"}) is not None
    assert test_db.question.find_one({"problem": "Clone Graph"}) is not None


def test_admin_import_preview_rejects_duplicate_csv_rows(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one(
        {"name": "Admin", "email": "admin@example.com", "is_admin": True, "progress": {}}
    ).inserted_id
    csv_text = "\n".join(
        [
            "topic_name,topic_position,problem,url,url2,difficulty,position",
            "Array,0,Two Sum,https://leetcode.com/problems/two-sum/,,Easy,0",
            "Array,0,Two Sum,https://leetcode.com/problems/two-sum/,,Easy,1",
        ]
    )

    with flask_app.test_client() as client:
        login_as(client, admin_id)
        response = client.post(
            "/admin/import-sheet",
            data={"sheet_file": (io.BytesIO(csv_text.encode("utf-8")), "sheet.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "duplicate question row detected" in body.lower()
    assert test_db.question.count_documents({}) == 0
