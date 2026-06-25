from pathlib import Path

from conftest import build_test_app, login_test_user


BASE_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "base.html"
).read_text(encoding="utf-8")


def set_csrf_token(client, token="test-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def test_logout_route_rejects_get_and_keeps_session(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {"email": "user@example.com", "progress": {}, "is_admin": False}
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        csrf_token = set_csrf_token(client)

        response = client.get("/logout")

        assert response.status_code == 405
        with client.session_transaction() as session:
            assert session.get("_user_id") == str(user_id)
            assert session.get("csrf_token") == csrf_token


def test_logout_route_requires_matching_csrf_token(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {"email": "user@example.com", "progress": {}, "is_admin": False}
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        set_csrf_token(client, "expected-token")

        response = client.post("/logout", data={"csrf_token": "wrong-token"})

        assert response.status_code == 403
        with client.session_transaction() as session:
            assert session.get("_user_id") == str(user_id)


def test_logout_route_logs_user_out_with_valid_csrf_token(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {"email": "user@example.com", "progress": {}, "is_admin": False}
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        csrf_token = set_csrf_token(client)

        response = client.post("/logout", data={"csrf_token": csrf_token})

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"
        with client.session_transaction() as session:
            assert "_user_id" not in session


def test_sidebar_logout_uses_post_form_with_csrf_token():
    assert 'action="{{ url_for(\'auth.logout\') }}"' in BASE_TEMPLATE
    assert 'method="post"' in BASE_TEMPLATE
    assert 'name="csrf_token"' in BASE_TEMPLATE
    assert 'id="nav-logout"' in BASE_TEMPLATE
