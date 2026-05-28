from datetime import datetime, timezone, timedelta
from bson import ObjectId
import mongomock

import app as app_module
import app.admin.routes as admin_routes
from tests.test_admin_routes import create_test_app, login_as, set_csrf_token


def test_link_checker_access_denied_when_not_logged_in(monkeypatch):
    flask_app, _ = create_test_app(monkeypatch)
    
    with flask_app.test_client() as client:
        response = client.get("/admin/link-checker")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        
        response = client.post("/admin/link-checker/start")
        assert response.status_code == 403


def test_link_checker_access_denied_when_normal_user(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one({
        "name": "Normal",
        "email": "normal@example.com",
        "is_admin": False,
        "progress": {}
    }).inserted_id
    
    with flask_app.test_client() as client:
        login_as(client, user_id)
        response = client.get("/admin/link-checker")
        assert response.status_code == 403
        
        response = client.post("/admin/link-checker/start")
        assert response.status_code == 403


def test_link_checker_dashboard_renders_for_admin(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one({
        "name": "Admin User",
        "email": "admin@example.com",
        "is_admin": True,
        "progress": {}
    }).inserted_id
    
    # Seed a question with multiple links
    test_db.question.insert_one({
        "problem": "Reverse String",
        "url": "https://leetcode.com/problems/reverse-string/",
        "url2": "https://practice.geeksforgeeks.org/problems/reverse-a-string/1",
        "editorial_links": ["https://www.geeksforgeeks.org/reverse-a-string/"]
    })
    
    # Seed some cached broken results
    test_db.link_checks.insert_one({
        "_id": "https://practice.geeksforgeeks.org/problems/reverse-a-string/1",
        "status": "broken",
        "status_code": 404,
        "checked_at": datetime.now(timezone.utc)
    })
    
    with flask_app.test_client() as client:
        login_as(client, admin_id)
        response = client.get("/admin/link-checker")
        
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Broken-Link Checker" in body
    assert "Reverse String" in body
    assert "https://practice.geeksforgeeks.org" in body
    assert "broken" in body


def test_link_checker_start_and_status_api(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one({
        "name": "Admin",
        "email": "admin@example.com",
        "is_admin": True,
        "progress": {}
    }).inserted_id
    
    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        
        # Test start
        response = client.post("/admin/link-checker/start", headers={"X-CSRFToken": csrf_token})
        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        
        # Test status
        response = client.get("/admin/link-checker/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "is_running" in data
        assert "completed_links" in data
        assert "total_links" in data


def test_link_checker_clear_cache_api(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    admin_id = test_db.user.insert_one({
        "name": "Admin",
        "email": "admin@example.com",
        "is_admin": True,
        "progress": {}
    }).inserted_id
    
    # Seed checks
    test_db.link_checks.insert_one({"_id": "http://foo.bar", "status": "ok"})
    test_db.link_checks.insert_one({"_id": "http://stale.link", "status": "broken"})
    
    with flask_app.test_client() as client:
        login_as(client, admin_id)
        csrf_token = set_csrf_token(client)
        
        # Clear cache
        response = client.post("/admin/link-checker/clear", headers={"X-CSRFToken": csrf_token})
        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        
        # Ensure collection is empty
        assert test_db.link_checks.count_documents({}) == 0
        
        status_doc = test_db.link_checker_status.find_one({"_id": "status"})
        assert status_doc["summary"] == "Checked links cache cleared."
