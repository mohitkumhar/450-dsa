import pyotp

import app.auth.routes as auth_routes
from conftest import build_test_app


def _create_password_user(test_db, password_hash, **extra_fields):
    user_doc = {
        "name": "Secure User",
        "email": "secure@example.com",
        "password": password_hash,
        "progress": {},
        "is_admin": False,
    }
    user_doc.update(extra_fields)
    return test_db.user.insert_one(user_doc).inserted_id


def test_login_redirects_two_factor_users_to_verification(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    password_hash = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    secret = pyotp.random_base32()
    _create_password_user(
        test_db,
        password_hash,
        two_factor_enabled=True,
        two_factor_secret=secret,
        two_factor_backup_codes=[],
    )

    response = flask_app.test_client().post(
        "/login",
        data={"email": "secure@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 302
    assert "/login/verify-2fa" in response.headers["Location"]


def test_two_factor_setup_confirmation_persists_secret_and_backup_codes(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    password_hash = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    user_id = _create_password_user(test_db, password_hash)

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
            session["two_factor_pending_secret"] = pyotp.random_base32()
            session["two_factor_pending_backup_codes"] = ["ABCD-EFGH", "WXYZ-1234"]
            secret = session["two_factor_pending_secret"]

        response = client.post(
            "/settings/two-factor/confirm",
            data={"password": "StrongPass1!", "code": pyotp.TOTP(secret).now()},
        )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings/two-factor")
    assert user_doc["two_factor_enabled"] is True
    assert user_doc["two_factor_secret"] == secret
    assert len(user_doc["two_factor_backup_codes"]) == 2
    assert user_doc["two_factor_backup_codes"][0] != "ABCD-EFGH"


def test_verify_two_factor_login_accepts_valid_totp_code(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    password_hash = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    secret = pyotp.random_base32()
    user_id = _create_password_user(
        test_db,
        password_hash,
        two_factor_enabled=True,
        two_factor_secret=secret,
        two_factor_backup_codes=[],
    )

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["two_factor_pending_user_id"] = str(user_id)

        response = client.post(
            "/login/verify-2fa",
            data={"code": pyotp.TOTP(secret).now()},
        )

        with client.session_transaction() as session:
            assert session.get("_user_id") == str(user_id)
            assert "two_factor_pending_user_id" not in session

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_backup_code_sign_in_consumes_code(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    password_hash = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    backup_code = "ABCD-EFGH"
    user_id = _create_password_user(
        test_db,
        password_hash,
        two_factor_enabled=True,
        two_factor_secret=pyotp.random_base32(),
        two_factor_backup_codes=auth_routes.hash_backup_codes([backup_code]),
    )

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["two_factor_pending_user_id"] = str(user_id)

        response = client.post("/login/verify-2fa", data={"code": backup_code})

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert user_doc["two_factor_backup_codes"] == []


def test_oauth_only_users_cannot_start_two_factor_setup(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "OAuth User",
            "email": "oauth@example.com",
            "google_id": "google-1",
            "progress": {},
            "is_admin": False,
        }
    ).inserted_id

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

        response = client.post("/settings/two-factor/setup")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings/two-factor")
