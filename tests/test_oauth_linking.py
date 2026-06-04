from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from bson import ObjectId

EXISTING_USER_ID = ObjectId()

GITHUB_USER_INFO = {
    "id": 12345,
    "name": "Test User",
    "login": "testuser",
}

GITHUB_EMAILS = [{"email": "test@example.com", "primary": True, "verified": True}]

GOOGLE_USER_INFO = {
    "sub": "google-999",
    "name": "Google User",
    "email": "test@example.com",
}


def make_fake_db(existing=None, inserted=None):

    class FakeUserCollection:
        @staticmethod
        def find_one(q):
            if existing and q.get("email"):
                return existing
            if existing and q.get("github_id"):
                return None
            if existing and q.get("google_id"):
                return None
            if inserted and q.get("_id"):
                return {**inserted, "_id": inserted.get("_id")}
            return None

        @staticmethod
        def update_one(f, u):
            if existing:
                existing.update(u.get("$set", {}))

        @staticmethod
        def insert_one(doc):
            doc["_id"] = ObjectId()
            if inserted is not None:
                inserted.update(doc)
            return SimpleNamespace(inserted_id=doc.get("_id", ObjectId()))

        @staticmethod
        def update_many(f, u):
            pass

        @staticmethod
        def create_index(*a, **kw):
            pass

    class FakeTopicCollection:
        @staticmethod
        def create_index(*a, **kw):
            pass

        @staticmethod
        def count_documents(*a, **kw):
            return 1

        @staticmethod
        def insert_one(*a, **kw):
            return SimpleNamespace(inserted_id="topic-1")

        @staticmethod
        def insert_many(*a, **kw):
            pass

    class FakeQuestionCollection:
        @staticmethod
        def create_index(*a, **kw):
            pass

        @staticmethod
        def count_documents(*a, **kw):
            return 0

        @staticmethod
        def insert_one(*a, **kw):
            return SimpleNamespace(inserted_id="q-1")

        @staticmethod
        def insert_many(*a, **kw):
            pass

    class FakeDB:
        user = FakeUserCollection()
        topic = FakeTopicCollection()
        question = FakeQuestionCollection()

    return FakeDB()


def make_app(monkeypatch, db_override):
    import app as app_module
    import app.auth.routes as auth_routes
    import app.extensions as ext

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(app_module, "db", db_override)
    monkeypatch.setattr(auth_routes, "db", db_override)
    monkeypatch.setattr(ext, "db", db_override)
    monkeypatch.setattr(ext.mongo, "db", db_override, raising=False)

    monkeypatch.setattr(ext.mongo, "init_app", lambda a, **kwargs: None)
    monkeypatch.setattr(ext.oauth, "init_app", lambda a: None)
    monkeypatch.setattr(ext.limiter, "init_app", lambda a: None)
    monkeypatch.setattr(ext.cache, "init_app", lambda a: None)
    monkeypatch.setattr(ext.oauth, "register", lambda name, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


def _make_github_mock(token=True, user_ok=True):
    mock = MagicMock()
    mock.authorize_access_token = MagicMock(
        return_value={"access_token": "tok"} if token else None
    )
    user_resp = MagicMock()
    user_resp.ok = user_ok
    user_resp.json = MagicMock(return_value=GITHUB_USER_INFO)
    email_resp = MagicMock()
    email_resp.status_code = 200
    email_resp.json = MagicMock(return_value=GITHUB_EMAILS)
    mock.get = MagicMock(
        side_effect=lambda url: user_resp if url == "user" else email_resp
    )
    return mock


def _make_google_mock(user_info=GOOGLE_USER_INFO):
    mock = MagicMock()
    mock.authorize_access_token = MagicMock(return_value={"access_token": "tok"})
    mock.parse_id_token = MagicMock(return_value=user_info)
    mock.userinfo = MagicMock(return_value=user_info)
    return mock


def _get_flashed_messages(client):
    with client.session_transaction() as session:
        return list(session.get("_flashes", []))


# ── GitHub Tests ──────────────────────────────────────────────────────────────


def test_github_links_existing_email_user(monkeypatch):
    existing = {"_id": EXISTING_USER_ID, "email": "test@example.com", "progress": {}}
    db = make_fake_db(existing=existing)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=_make_github_mock()):
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 302
            assert "github_id" in existing


def test_github_creates_new_user_when_no_match(monkeypatch):
    inserted = {}
    db = make_fake_db(inserted=inserted)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=_make_github_mock()):
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 302
            assert inserted.get("github_id") == str(GITHUB_USER_INFO["id"])


def test_github_missing_token_returns_400(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=_make_github_mock(token=False)):
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 400


def test_github_failed_user_fetch_returns_400(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=_make_github_mock(user_ok=False)):
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 400


def test_github_token_exchange_exception_redirects_to_login(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(side_effect=RuntimeError("secret boom"))

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=mock):
            resp = client.get("/login/github/authorize")

        flashes = _get_flashed_messages(client)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert (
        "danger",
        "GitHub sign-in is temporarily unavailable. Please try again.",
    ) in flashes
    assert all("secret boom" not in message for _, message in flashes)


def test_github_user_fetch_exception_redirects_to_login(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(return_value={"access_token": "tok"})
    mock.get = MagicMock(side_effect=RuntimeError("provider outage"))

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=mock):
            resp = client.get("/login/github/authorize")

        flashes = _get_flashed_messages(client)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert (
        "danger",
        "GitHub sign-in is temporarily unavailable. Please try again.",
    ) in flashes
    assert all("provider outage" not in message for _, message in flashes)


def test_github_email_fetch_exception_does_not_fail_login(monkeypatch):
    inserted = {}
    db = make_fake_db(inserted=inserted)
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(return_value={"access_token": "tok"})
    user_resp = MagicMock()
    user_resp.ok = True
    user_resp.json = MagicMock(return_value=GITHUB_USER_INFO)
    mock.get = MagicMock(
        side_effect=lambda url: (
            user_resp
            if url == "user"
            else (_ for _ in ()).throw(RuntimeError("email fetch down"))
        )
    )

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github", new=mock):
            resp = client.get("/login/github/authorize")

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    assert inserted.get("github_id") == str(GITHUB_USER_INFO["id"])


# ── Google Tests ──────────────────────────────────────────────────────────────


def test_google_links_existing_email_user(monkeypatch):
    existing = {"_id": EXISTING_USER_ID, "email": "test@example.com", "progress": {}}
    db = make_fake_db(existing=existing)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.google", new=_make_google_mock()):
            with client.session_transaction() as sess:
                sess["google_oauth_nonce"] = "test-nonce"
            resp = client.get("/login/google/authorize")
            assert resp.status_code == 302
            assert "google_id" in existing


def test_google_creates_new_user_when_no_match(monkeypatch):
    inserted = {}
    db = make_fake_db(inserted=inserted)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.google", new=_make_google_mock()):
            with client.session_transaction() as sess:
                sess["google_oauth_nonce"] = "test-nonce"
            resp = client.get("/login/google/authorize")
            assert resp.status_code == 302
            assert inserted.get("google_id") == "google-999"


def test_google_missing_userinfo_returns_400(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(return_value={"access_token": "tok"})
    mock.parse_id_token = MagicMock(return_value=None)
    mock.userinfo = MagicMock(return_value=None)

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["google_oauth_nonce"] = "test-nonce"
        with patch("app.auth.routes.google", new=mock):
            resp = client.get("/login/google/authorize")
            assert resp.status_code == 400


def test_google_token_exchange_exception_redirects_to_login(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(side_effect=RuntimeError("token failed"))

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["google_oauth_nonce"] = "test-nonce"
        with patch("app.auth.routes.google", new=mock):
            resp = client.get("/login/google/authorize")

        flashes = _get_flashed_messages(client)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert (
        "danger",
        "Google sign-in is temporarily unavailable. Please try again.",
    ) in flashes
    assert all("token failed" not in message for _, message in flashes)


def test_google_id_token_parsing_exception_redirects_to_login(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(return_value={"access_token": "tok"})
    mock.parse_id_token = MagicMock(side_effect=RuntimeError("parse failed"))

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["google_oauth_nonce"] = "test-nonce"
        with patch("app.auth.routes.google", new=mock):
            resp = client.get("/login/google/authorize")

        flashes = _get_flashed_messages(client)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert (
        "danger",
        "Google sign-in is temporarily unavailable. Please try again.",
    ) in flashes
    assert all("parse failed" not in message for _, message in flashes)


def test_google_userinfo_exception_redirects_to_login_when_id_token_missing(
    monkeypatch,
):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    mock = MagicMock()
    mock.authorize_access_token = MagicMock(return_value={"access_token": "tok"})
    mock.parse_id_token = MagicMock(return_value=None)
    mock.userinfo = MagicMock(side_effect=RuntimeError("userinfo failed"))

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["google_oauth_nonce"] = "test-nonce"
        with patch("app.auth.routes.google", new=mock):
            resp = client.get("/login/google/authorize")

        flashes = _get_flashed_messages(client)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert (
        "danger",
        "Google sign-in is temporarily unavailable. Please try again.",
    ) in flashes
    assert all("userinfo failed" not in message for _, message in flashes)


def test_resolve_oauth_user_returns_existing_provider_match(monkeypatch):
    import app.auth.routes as auth_routes

    existing = {
        "_id": EXISTING_USER_ID,
        "email": "test@example.com",
        "github_id": str(GITHUB_USER_INFO["id"]),
        "progress": {},
    }

    class FakeUserCollection:
        @staticmethod
        def find_one(q):
            if q.get("github_id") == str(GITHUB_USER_INFO["id"]):
                return existing
            return None

        @staticmethod
        def update_one(*args, **kwargs):
            raise AssertionError("provider-matched users should not be relinked")

        @staticmethod
        def insert_one(*args, **kwargs):
            raise AssertionError("provider-matched users should not be recreated")

    class FakeDB:
        user = FakeUserCollection()

    db = FakeDB()
    monkeypatch.setattr(auth_routes, "db", db)

    user_doc, action = auth_routes.resolve_oauth_user(
        "github_id",
        str(GITHUB_USER_INFO["id"]),
        "Ignored Name",
        email="other@example.com",
    )

    assert action == "existing"
    assert user_doc["_id"] == EXISTING_USER_ID
    assert user_doc["github_id"] == str(GITHUB_USER_INFO["id"])


def test_resolve_oauth_user_links_existing_email_match(monkeypatch):
    import app.auth.routes as auth_routes

    existing = {"_id": EXISTING_USER_ID, "email": "test@example.com", "progress": {}}
    db = make_fake_db(existing=existing)
    monkeypatch.setattr(auth_routes, "db", db)

    user_doc, action = auth_routes.resolve_oauth_user(
        "google_id",
        GOOGLE_USER_INFO["sub"],
        GOOGLE_USER_INFO["name"],
        email=GOOGLE_USER_INFO["email"],
    )

    assert action == "linked"
    assert user_doc["_id"] == EXISTING_USER_ID
    assert user_doc["google_id"] == GOOGLE_USER_INFO["sub"]


def test_resolve_oauth_user_creates_new_user_without_email(monkeypatch):
    import app.auth.routes as auth_routes

    inserted = {}
    db = make_fake_db(inserted=inserted)
    monkeypatch.setattr(auth_routes, "db", db)

    user_doc, action = auth_routes.resolve_oauth_user(
        "github_id",
        str(GITHUB_USER_INFO["id"]),
        GITHUB_USER_INFO["login"],
        email=None,
    )

    assert action == "created"
    assert user_doc["github_id"] == str(GITHUB_USER_INFO["id"])
    assert user_doc["email"] is None


def test_login_page_renders_google_button(monkeypatch):
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        resp = client.get("/login")

        assert resp.status_code == 200

        assert b"login/google" in resp.data
