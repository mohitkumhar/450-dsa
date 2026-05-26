import app.auth.routes as auth_routes
from conftest import build_test_app, csrf_headers


def test_register_stores_normalized_email(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(
        auth_routes.bcrypt,
        "generate_password_hash",
        lambda password: b"hashed-password",
    )

    with flask_app.test_client() as client:
        response = client.post(
            "/register",
            data={
                "name": "Case User",
                "email": "  USER@Example.COM  ",
                "password": "StrongPass1!",
                "confirm_password": "StrongPass1!",
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 302
    assert test_db.user.find_one({"email": "user@example.com"}) is not None
    assert test_db.user.find_one({"email": "USER@Example.COM"}) is None


def test_login_looks_up_normalized_email(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(auth_routes.bcrypt, "check_password_hash", lambda stored, password: True)

    test_db.user.insert_one(
        {
            "name": "Case User",
            "email": "user@example.com",
            "password": "hashed-password",
            "progress": {},
        }
    )

    with flask_app.test_client() as client:
        response = client.post(
            "/login",
            data={"email": " USER@Example.COM ", "password": "strong-password"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_email_normalizer_handles_empty_values():
    assert auth_routes.normalize_email(None) == ""
    assert auth_routes.normalize_email("") == ""
    assert auth_routes.normalize_email(" Test@Example.COM ") == "test@example.com"
