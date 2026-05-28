from datetime import datetime, timezone
import mongomock
from bson import ObjectId
import pytest

import app as app_module
import app.tracker.routes as tracker_routes
import app.admin.routes as admin_routes
import app.auth.routes as auth_routes
from conftest import build_test_app, csrf_headers, login_test_user, set_csrf_token


def create_test_app(monkeypatch):
    test_db = mongomock.MongoClient().db
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(tracker_routes, "db", test_db)
    monkeypatch.setattr(admin_routes, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)

    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True

    return flask_app, test_db


def test_submit_report_requires_login(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        set_csrf_token(client)
        response = client.post(
            "/report_question",
            json={
                "question_id": str(question_id),
                "report_type": "broken_link",
                "description": "The link is completely broken."
            },
            headers=csrf_headers(client)
        )

    # login_required triggers redirect (302) or 401 depending on Flask-Login setup.
    # Flask-Login defaults to redirecting to login page (302).
    assert response.status_code == 302


def test_submit_report_success(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    question_id = test_db.question.insert_one({"problem": "Two Sum", "url": "https://leetcode.com/two-sum"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        # Update user name
        test_db.user.update_one({"_id": user_id}, {"$set": {"name": "Test User"}})
        
        response = client.post(
            "/report_question",
            json={
                "question_id": str(question_id),
                "report_type": "broken_link",
                "description": "The link is completely broken."
            },
            headers=csrf_headers(client)
        )

    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data["success"] is True
    assert res_data["message"] == "Report submitted successfully!"

    # Verify document in db
    reports = list(test_db.reports.find())
    assert len(reports) == 1
    report = reports[0]
    assert report["question_id"] == question_id
    assert report["question_name"] == "Two Sum"
    assert report["report_type"] == "broken_link"
    assert report["description"] == "The link is completely broken."
    assert report["reporter_id"] == user_id
    assert report["reporter_name"] == "Test User"
    assert report["status"] == "pending"
    assert "created_at" in report


def test_submit_report_validation(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)

        # 1. Invalid report type
        response = client.post(
            "/report_question",
            json={
                "question_id": str(question_id),
                "report_type": "invalid_type",
                "description": "Some description"
            },
            headers=csrf_headers(client)
        )
        assert response.status_code == 400
        assert "Invalid report type" in response.get_json()["error"]

        # 2. Empty description
        response = client.post(
            "/report_question",
            json={
                "question_id": str(question_id),
                "report_type": "broken_link",
                "description": "   "
            },
            headers=csrf_headers(client)
        )
        assert response.status_code == 400
        assert "Description cannot be empty" in response.get_json()["error"]

        # 3. Question not found
        response = client.post(
            "/report_question",
            json={
                "question_id": str(ObjectId()),
                "report_type": "broken_link",
                "description": "Valid description"
            },
            headers=csrf_headers(client)
        )
        assert response.status_code == 404
        assert "Question not found" in response.get_json()["error"]


def test_admin_reports_dashboard_access_control(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)

    # 1. Anonymous user redirected to login
    with flask_app.test_client() as client:
        response = client.get("/admin/reports")
    assert response.status_code == 302

    # 2. Non-admin user gets 403
    with flask_app.test_client() as client:
        user_id = test_db.user.insert_one({
            "name": "Normal User",
            "email": "normal@example.com",
            "is_admin": False,
            "progress": {}
        }).inserted_id
        login_test_user(client, user_id)
        response = client.get("/admin/reports")
    assert response.status_code == 403


def test_admin_reports_dashboard_success(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    question_id = test_db.question.insert_one({"problem": "Two Sum", "url": "https://leetcode.com/two-sum"}).inserted_id
    
    # Insert some reports
    test_db.reports.insert_many([
        {
            "question_id": question_id,
            "question_name": "Two Sum",
            "report_type": "broken_link",
            "description": "Link doesn't work.",
            "reporter_name": "Reporter One",
            "status": "pending",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "question_id": question_id,
            "question_name": "Two Sum",
            "report_type": "typo",
            "description": "Typo in details.",
            "reporter_name": "Reporter Two",
            "status": "resolved",
            "created_at": datetime.now(timezone.utc)
        }
    ])

    with flask_app.test_client() as client:
        admin_id = test_db.user.insert_one({
            "name": "Admin User",
            "email": "admin@example.com",
            "is_admin": True,
            "progress": {}
        }).inserted_id
        login_test_user(client, admin_id)
        response = client.get("/admin/reports")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "In-App Metadata Reports" in html
    assert "Link doesn&#39;t work." in html or "Link doesn't work." in html
    assert "Typo in details." in html
    assert "Reporter One" in html
    assert "Reporter Two" in html
    
    # Verify KPI counts are rendered
    assert "Pending Reviews" in html
    assert "Resolved" in html


def test_admin_update_report_status(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    report_id = test_db.reports.insert_one({
        "question_name": "Two Sum",
        "report_type": "broken_link",
        "description": "Broken link",
        "status": "pending"
    }).inserted_id

    # 1. Non-admin gets 403
    with flask_app.test_client() as client:
        user_id = test_db.user.insert_one({
            "name": "Normal User",
            "email": "normal@example.com",
            "is_admin": False,
            "progress": {}
        }).inserted_id
        login_test_user(client, user_id)
        response = client.post(
            f"/admin/reports/{report_id}/status",
            json={"status": "reviewed"},
            headers=csrf_headers(client)
        )
    assert response.status_code == 403

    # 2. Admin successfully updates status
    with flask_app.test_client() as client:
        admin_id = test_db.user.insert_one({
            "name": "Admin User",
            "email": "admin@example.com",
            "is_admin": True,
            "progress": {}
        }).inserted_id
        login_test_user(client, admin_id)
        
        response = client.post(
            f"/admin/reports/{report_id}/status",
            json={"status": "resolved"},
            headers=csrf_headers(client)
        )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    
    # Verify update in database
    report = test_db.reports.find_one({"_id": report_id})
    assert report["status"] == "resolved"
