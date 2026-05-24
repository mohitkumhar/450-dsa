import mongomock

import app as app_module
import app.auth.routes as auth_routes


def create_test_app(monkeypatch):
    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True
    return flask_app, test_db


def test_register_rejects_weak_password_before_insert(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)

    response = flask_app.test_client().post(
        "/register",
        data={
            "name": "Weak User",
            "email": "weak@example.com",
            "password": "password",
            "confirm_password": "password",
        },
    )

    assert response.status_code == 302
    assert "/register" in response.headers["Location"]
    assert test_db.user.find_one({"email": "weak@example.com"}) is None


def test_register_rejects_mismatched_confirmation(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)

    response = flask_app.test_client().post(
        "/register",
        data={
            "name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass2!",
        },
    )

    assert response.status_code == 302
    assert "/register" in response.headers["Location"]
    assert test_db.user.find_one({"email": "mismatch@example.com"}) is None


def test_register_accepts_strong_confirmed_password(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)

    response = flask_app.test_client().post(
        "/register",
        data={
            "name": "Strong User",
            "email": "strong@example.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
        },
    )

    user_doc = test_db.user.find_one({"email": "strong@example.com"})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert user_doc is not None
    assert user_doc["password"] != "StrongPass1!"
    assert auth_routes.bcrypt.check_password_hash(user_doc["password"], "StrongPass1!")


def test_password_validator_reports_missing_requirements():
    errors = auth_routes.validate_registration_password("longpassword", "longpassword")

    assert "Password must include at least one uppercase letter." in errors
    assert "Password must include at least one number." in errors
    assert "Password must include at least one special character." in errors
