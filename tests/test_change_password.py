from app.auth.routes import bcrypt
from conftest import build_test_app, login_test_user


def set_csrf_token(client, token="test-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def create_password_user(test_db, *, password="StrongPass1!"):
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    return test_db.user.insert_one(
        {
            "name": "Password User",
            "email": "password@example.com",
            "password": hashed_password,
            "progress": {},
            "is_admin": False,
        }
    ).inserted_id


def test_change_password_rejects_wrong_current_password(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = create_password_user(test_db)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    token = set_csrf_token(client)

    response = client.post(
        "/change_password",
        data={
            "csrf_token": token,
            "current_password": "WrongPass1!",
            "new_password": "BetterPass2@",
            "confirm_password": "BetterPass2@",
        },
    )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert bcrypt.check_password_hash(user_doc["password"], "StrongPass1!")


def test_change_password_rejects_weak_new_password(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = create_password_user(test_db)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    token = set_csrf_token(client)

    response = client.post(
        "/change_password",
        data={
            "csrf_token": token,
            "current_password": "StrongPass1!",
            "new_password": "password",
            "confirm_password": "password",
        },
    )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert bcrypt.check_password_hash(user_doc["password"], "StrongPass1!")


def test_change_password_rejects_same_password(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = create_password_user(test_db)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    token = set_csrf_token(client)

    response = client.post(
        "/change_password",
        data={
            "csrf_token": token,
            "current_password": "StrongPass1!",
            "new_password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
        },
    )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert bcrypt.check_password_hash(user_doc["password"], "StrongPass1!")


def test_change_password_updates_password_for_valid_request(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = create_password_user(test_db)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    token = set_csrf_token(client)

    response = client.post(
        "/change_password",
        data={
            "csrf_token": token,
            "current_password": "StrongPass1!",
            "new_password": "BetterPass2@",
            "confirm_password": "BetterPass2@",
        },
    )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert bcrypt.check_password_hash(user_doc["password"], "BetterPass2@")
    assert not bcrypt.check_password_hash(user_doc["password"], "StrongPass1!")


def test_change_password_rejects_invalid_csrf(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = create_password_user(test_db)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    set_csrf_token(client)

    response = client.post(
        "/change_password",
        data={
            "csrf_token": "wrong-token",
            "current_password": "StrongPass1!",
            "new_password": "BetterPass2@",
            "confirm_password": "BetterPass2@",
        },
    )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 403
    assert bcrypt.check_password_hash(user_doc["password"], "StrongPass1!")


def test_change_password_rejects_oauth_only_user(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "OAuth User",
            "email": "oauth@example.com",
            "progress": {},
            "is_admin": False,
        }
    ).inserted_id
    client = flask_app.test_client()
    login_test_user(client, user_id)
    token = set_csrf_token(client)

    response = client.post(
        "/change_password",
        data={
            "csrf_token": token,
            "current_password": "StrongPass1!",
            "new_password": "BetterPass2@",
            "confirm_password": "BetterPass2@",
        },
    )

    user_doc = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    assert "password" not in user_doc
