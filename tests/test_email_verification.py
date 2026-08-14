import app.auth.routes as auth_routes
from conftest import build_test_app, csrf_headers
from app.extensions import bcrypt


def _create_user(test_db, email, password, is_verified=True, verification_token=""):
    test_db.user.insert_one(
        {
            "name": "Test User",
            "email": email,
            "password": bcrypt.generate_password_hash(password).decode("utf-8"),
            "progress": {},
            "is_admin": False,
            "is_verified": is_verified,
            "verification_token": verification_token,
        }
    )


def test_login_blocked_when_unverified(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    
    _create_user(test_db, "unverified@example.com", "Password123!", is_verified=False)

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/login",
            data={"email": "unverified@example.com", "password": "Password123!"},
            headers=headers,
        )

    assert response.status_code == 302
    assert response.location == "/login"
    
    with client.session_transaction() as session:
        flashes = session.get("_flashes", [])
        assert any(b"Please verify your email" in msg[1].encode('utf-8') for msg in flashes)


def test_login_success_when_verified(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    
    _create_user(test_db, "verified@example.com", "Password123!", is_verified=True)

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/login",
            data={"email": "verified@example.com", "password": "Password123!"},
            headers=headers,
        )

    assert response.status_code == 302
    assert response.location == "/"
    
    
def test_verify_email_route(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    
    _create_user(test_db, "unverified@example.com", "Password123!", is_verified=False, verification_token="test-token")

    with flask_app.test_client() as client:
        response = client.get("/verify-email/test-token")
        
    assert response.status_code == 302
    assert response.location == "/login"
    
    user = test_db.user.find_one({"email": "unverified@example.com"})
    assert user["is_verified"] is True
    assert "verification_token" not in user


def test_registration_creates_unverified_user(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)
    
    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/register",
            data={
                "name": "New User",
                "email": "newuser@example.com",
                "password": "Password123!",
                "confirm_password": "Password123!"
            },
            headers=headers,
        )

    assert response.status_code == 302
    assert response.location == "/login"

    user = test_db.user.find_one({"email": "newuser@example.com"})
    assert user is not None
    assert user["is_verified"] is False
    assert user["verification_token"] is not None
    assert len(user["verification_token"]) > 0


def test_resend_verification_updates_token(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)

    _create_user(test_db, "resend@example.com", "Password123!", is_verified=False, verification_token="old-token")

    with flask_app.test_client() as client:
        headers = csrf_headers(client)
        response = client.post(
            "/resend-verification",
            data={"email": "resend@example.com"},
            headers=headers,
        )

    assert response.status_code == 302
    assert response.location == "/login"

    user = test_db.user.find_one({"email": "resend@example.com"})
    assert user is not None
    assert user["verification_token"] != "old-token"
    assert user["verification_token"]
