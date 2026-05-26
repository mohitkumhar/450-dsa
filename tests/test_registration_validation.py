import app.auth.routes as auth_routes
from conftest import build_test_app, set_csrf_token


def test_register_rejects_blank_display_name(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)

    with flask_app.test_client() as client:
        csrf_token = set_csrf_token(client)
        response = client.post(
            "/register",
            data={
                "name": "   ",
                "email": "blank-name@example.com",
                "password": "StrongPass1!",
                "confirm_password": "StrongPass1!",
                "csrf_token": csrf_token,
            },
        )

    assert response.status_code == 302
    assert test_db.user.count_documents({"email": "blank-name@example.com"}) == 0
