import mongomock

import app as app_module
import app.auth.routes as auth_routes


class FakeGoogleClient:
    def __init__(self, parsed_user=None):
        self.authorize_redirect_calls = []
        self.authorize_access_token_called = False
        self.parse_id_token_calls = []
        self.userinfo_called = False
        self.parsed_user = parsed_user or {
            "sub": "google-user-1",
            "email": "google@example.com",
            "name": "Google User",
        }

    def authorize_redirect(self, redirect_uri, **kwargs):
        self.authorize_redirect_calls.append((redirect_uri, kwargs))
        return "redirected"

    def authorize_access_token(self):
        self.authorize_access_token_called = True
        return {"id_token": "token"}

    def parse_id_token(self, token, nonce=None):
        self.parse_id_token_calls.append((token, nonce))
        return self.parsed_user

    def userinfo(self):
        self.userinfo_called = True
        return self.parsed_user


def create_test_app(monkeypatch, google_client):
    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(auth_routes, "google", google_client)

    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True

    return flask_app, test_db


def test_google_login_generates_and_sends_nonce(monkeypatch):
    google_client = FakeGoogleClient()
    flask_app, _ = create_test_app(monkeypatch, google_client)

    with flask_app.test_client() as client:
        response = client.get("/login/google")

        with client.session_transaction() as session:
            stored_nonce = session[auth_routes.GOOGLE_OAUTH_NONCE_SESSION_KEY]

    assert response.status_code == 200
    assert google_client.authorize_redirect_calls
    redirect_uri, kwargs = google_client.authorize_redirect_calls[0]
    assert redirect_uri == "http://localhost/login/google/authorize"
    assert kwargs["nonce"] == stored_nonce


def test_google_authorize_uses_and_consumes_nonce(monkeypatch):
    google_client = FakeGoogleClient()
    flask_app, test_db = create_test_app(monkeypatch, google_client)

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session[auth_routes.GOOGLE_OAUTH_NONCE_SESSION_KEY] = "expected-nonce"

        response = client.get("/login/google/authorize")

        with client.session_transaction() as session:
            assert auth_routes.GOOGLE_OAUTH_NONCE_SESSION_KEY not in session

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert google_client.authorize_access_token_called is True
    assert google_client.parse_id_token_calls == [({"id_token": "token"}, "expected-nonce")]
    assert google_client.userinfo_called is False
    assert test_db.user.find_one({"google_id": "google-user-1"}) is not None


def test_google_authorize_rejects_missing_nonce(monkeypatch):
    google_client = FakeGoogleClient()
    flask_app, _ = create_test_app(monkeypatch, google_client)

    with flask_app.test_client() as client:
        response = client.get("/login/google/authorize")

    assert response.status_code == 400
    assert response.data == b"Google OAuth nonce missing"
    assert google_client.authorize_access_token_called is False
    assert google_client.parse_id_token_calls == []
