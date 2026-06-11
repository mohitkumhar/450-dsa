from datetime import datetime, timezone

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


def test_is_safe_url_validation():
    from app.admin.routes import is_safe_url
    
    # Allowed domains
    assert is_safe_url("https://leetcode.com/problems/reverse-string") is True
    assert is_safe_url("https://practice.geeksforgeeks.org/problems") is True
    assert is_safe_url("https://github.com/mohitkumhar/450-dsa") is True
    
    # Non-allowed domains
    assert is_safe_url("https://malicious-domain.com/hack") is False
    assert is_safe_url("http://google.com") is False
    
    # Loopback and private IPs
    assert is_safe_url("http://127.0.0.1/admin") is False
    assert is_safe_url("http://localhost:5000/") is False
    assert is_safe_url("http://192.168.1.1/router") is False
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False


def test_link_checker_ssrf_prevention(monkeypatch):
    import socket
    from app.admin.routes import run_link_scanner_sync
    flask_app, test_db = create_test_app(monkeypatch)
    
    # Seed questions with normal allowed URL and non-allowed URL
    test_db.question.insert_one({
        "problem": "SSRF test",
        "url": "https://malicious.com/attack",
        "url2": "https://leetcode.com/problems/safe"
    })
    
    # Mock socket.gethostbyname to return 127.0.0.1 for leetcode.com to simulate a DNS rebind SSRF
    def mock_gethostbyname(host):
        if "leetcode.com" in host:
            return "127.0.0.1"
        return "93.184.216.34"
    monkeypatch.setattr("socket.gethostbyname", mock_gethostbyname)
    
    # Run scanner synchronously
    run_link_scanner_sync(flask_app, lock_already_claimed=False)
    
    # Verify the checks in the DB
    check_malicious = test_db.link_checks.find_one({"_id": "https://malicious.com/attack"})
    assert check_malicious is not None
    assert check_malicious["status"] == "broken"
    assert "SSRF" in check_malicious["error_message"]
    
    check_safe_but_loopback = test_db.link_checks.find_one({"_id": "https://leetcode.com/problems/safe"})
    assert check_safe_but_loopback is not None
    assert check_safe_but_loopback["status"] == "broken"
    assert "SSRF" in check_safe_but_loopback["error_message"]


def test_link_checker_atomic_locking_concurrency(monkeypatch):
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
        
        # Claim lock first directly in DB to simulate another running process
        test_db.link_checker_status.update_one(
            {"_id": "status"},
            {"$set": {"is_running": True, "started_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        # Start link checker via web endpoint, should fail with 400
        response = client.post("/admin/link-checker/start", headers={"X-CSRFToken": csrf_token})
        assert response.status_code == 400
        assert response.get_json()["success"] is False
        assert "already running" in response.get_json()["error"]


def test_link_checker_cli_command(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    
    # Let's run the CLI command check-stale-links using the Flask test runner
    runner = flask_app.test_cli_runner()
    
    # Mock run_link_scanner_sync to verify it's called
    called = []
    def mock_run_scanner(app, lock_already_claimed):
        called.append(lock_already_claimed)
    
    monkeypatch.setattr("app.admin.routes.run_link_scanner_sync", mock_run_scanner)
    
    # Run the CLI command
    result = runner.invoke(args=["admin", "check-stale-links"])
    
    assert "Acquiring atomic running claim..." in result.output
    assert "Atomic lock claimed!" in result.output
    assert result.exit_code == 0
    assert called == [True]
    
    # The lock status should be set to true
    status = test_db.link_checker_status.find_one({"_id": "status"})
    assert status is not None
    assert status["is_running"] is True
