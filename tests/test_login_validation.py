import app.auth.routes as auth_routes
from conftest import build_test_app, csrf_headers
from app.extensions import bcrypt


def _create_user(test_db, email, password, name="Test User"):
    test_db.user.insert_one(
        {
            "name": name,
            "email": email,
            "password": bcrypt.generate_password_hash(password).decode("utf-8"),
            "progress": {},
            "is_admin": False,
        }
    )


def test_login_rejects_missing_password(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    _create_user(test_db, "test@example.com", "RealPass1!")

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/login",
            data={"email": "test@example.com"},
            headers=headers,
        )

    assert response.status_code == 200
    assert b"Login unsuccessful" in response.data


def test_login_rejects_empty_password(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    _create_user(test_db, "test2@example.com", "RealPass1!")

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/login",
            data={"email": "test2@example.com", "password": ""},
            headers=headers,
        )

    assert response.status_code == 200
    assert b"Login unsuccessful" in response.data


def test_login_rejects_missing_email(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/login",
            data={"password": "SomePass1!"},
            headers=headers,
        )

    assert response.status_code == 200
    assert b"Login unsuccessful" in response.data


def test_login_succeeds_with_valid_credentials(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    _create_user(test_db, "valid@example.com", "CorrectPass1!")

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/login",
            data={"email": "valid@example.com", "password": "CorrectPass1!"},
            headers=headers,
        )

    assert response.status_code == 302
