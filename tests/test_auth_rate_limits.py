from conftest import build_test_app, csrf_headers


def test_login_post_is_rate_limited_after_five_attempts(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)

    with flask_app.test_client() as client:
        for _ in range(5):
            response = client.post(
                "/login",
                data={"email": "missing@example.com", "password": "wrongpass"},
                headers=csrf_headers(client),
            )
            assert response.status_code == 200

        limited_response = client.post(
            "/login",
            data={"email": "missing@example.com", "password": "wrongpass"},
            headers=csrf_headers(client),
        )

    assert limited_response.status_code == 429
    assert limited_response.is_json
    assert limited_response.get_json()["error"] == "Too many requests"
    assert "message" in limited_response.get_json()
    assert "retry_after" in limited_response.get_json()


def test_register_post_is_rate_limited_after_three_attempts(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)

    with flask_app.test_client() as client:
        for attempt in range(3):
            response = client.post(
                "/register",
                data={
                    "name": "Rate Limited User",
                    "email": f"limited-{attempt}@example.com",
                    "password": "password",
                    "confirm_password": "password",
                },
                headers=csrf_headers(client),
            )
            assert response.status_code == 302

        limited_response = client.post(
            "/register",
            data={
                "name": "Rate Limited User",
                "email": "limited-final@example.com",
                "password": "password",
                "confirm_password": "password",
            },
            headers=csrf_headers(client),
        )

    assert test_db.user.count_documents({}) == 0
    assert limited_response.status_code == 429
    assert limited_response.is_json
    assert limited_response.get_json()["error"] == "Too many requests"
    assert "message" in limited_response.get_json()
    assert "retry_after" in limited_response.get_json()
