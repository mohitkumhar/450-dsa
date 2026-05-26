from types import SimpleNamespace

import app as app_module
import app.faq.routes as faq_routes
from app.config import DevelopmentConfig, ProductionConfig, TestingConfig
from app.extensions import login_manager


class FakeCollection:
    def __init__(self):
        self.indexes = []

    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))
        return None

    def count_documents(self, *args, **kwargs):
        return 1

    def insert_one(self, *args, **kwargs):
        return SimpleNamespace(inserted_id="topic-1")

    def insert_many(self, *args, **kwargs):
        return None

    def update_many(self, *args, **kwargs):
        return None


class FakeDB:
    def __init__(self):
        self.user = FakeCollection()
        self.topic = FakeCollection()
        self.question = FakeCollection()


def test_create_app_preserves_routes_and_blueprints(monkeypatch):
    registered_clients = []
    mongo_init_calls = []

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/450_dsa")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(
        app_module.mongo,
        "init_app",
        lambda flask_app, **kwargs: mongo_init_calls.append(kwargs),
    )
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(
        app_module.oauth,
        "register",
        lambda name, **kwargs: registered_clients.append(name),
    )

    flask_app = app_module.create_app()

    assert flask_app.config["MONGO_URI"] == "mongodb://localhost:27017/450_dsa"
    assert flask_app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"] == 5000
    assert flask_app.config["MONGO_CONNECT_TIMEOUT_MS"] == 5000
    assert flask_app.config["MONGO_MAX_POOL_SIZE"] == 20
    assert flask_app.config["MONGO_MIN_POOL_SIZE"] == 0
    assert flask_app.config["RATELIMIT_STORAGE_URI"] == "memory://"
    assert mongo_init_calls == [
        {
            "serverSelectionTimeoutMS": 5000,
            "connectTimeoutMS": 5000,
            "maxPoolSize": 20,
            "minPoolSize": 0,
        }
    ]
    assert login_manager.login_view == "auth.login"
    assert registered_clients == ["github", "google"]
    assert {"auth", "tracker", "profile", "leaderboard", "search", "admin", "public"} <= set(flask_app.blueprints)

    routes = {rule.rule for rule in flask_app.url_map.iter_rules()}
    assert "/" in routes
    assert "/login" in routes
    assert "/register" in routes
    assert "/logout" in routes
    assert "/login/github" in routes
    assert "/login/github/authorize" in routes
    assert "/login/google" in routes
    assert "/login/google/authorize" in routes
    assert "/topic/<topic_id>" in routes
    assert "/topic/<topic_id>/export-notes" in routes
    assert "/update_question/<question_id>" in routes
    assert "/bookmarks" in routes
    assert "/profile" in routes
    assert "/edit_profile" in routes
    assert "/upload_photo" in routes
    assert "/sync_platforms" in routes
    assert "/search_universities" in routes
    assert "/leaderboard" in routes
    assert "/api/leaderboard" in routes
    assert "/u/<user_id>" in routes
    assert "/search" in routes
    assert "/api/search_questions" in routes
    assert "/apidocs/" in routes
    assert "/apispec_1.json" in routes

    question_indexes = app_module.db.question.indexes
    topic_indexes = app_module.db.topic.indexes
    assert (("position",), {}) in topic_indexes
    assert (("topic",), {}) in question_indexes
    assert (([("problem", "text")],), {"name": "problem_text"}) in question_indexes
    assert "/admin" in routes
    assert "/admin/users/<user_id>/delete" in routes

    docs_response = flask_app.test_client().get("/apidocs/")
    assert docs_response.status_code == 200

    response = flask_app.test_client().get("/apispec_1.json")
    assert response.status_code == 200
    spec = response.get_json()
    assert "/api/search_questions" in spec["paths"]
    assert "/api/leaderboard" in spec["paths"]
    assert "/update_question/{question_id}" in spec["paths"]
    assert "/sync_platforms" in spec["paths"]
    assert "/edit_profile" in spec["paths"]
    assert "/upload_photo" in spec["paths"]


def test_create_app_serves_static_assets_with_cache_headers(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()

    response = flask_app.test_client().get("/static/css/main.css")

    assert response.status_code == 200
    assert response.cache_control.public is True
    assert response.cache_control.max_age == 86400


def test_create_app_caches_faq_page_render(monkeypatch):
    rendered_templates = []

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        faq_routes,
        "render_template",
        lambda template_name: rendered_templates.append(template_name) or "faq page",
    )

    flask_app = app_module.create_app()
    app_module.cache.clear()
    client = flask_app.test_client()

    first_response = client.get("/faq")
    second_response = client.get("/faq")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_data(as_text=True) == "faq page"
    assert second_response.get_data(as_text=True) == "faq page"
    assert rendered_templates == ["faq.html"]


def test_create_app_sets_secure_session_cookie_defaults(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()

    assert flask_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert flask_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert flask_app.config["SESSION_COOKIE_SECURE"] is True


def test_create_app_allows_insecure_session_cookie_in_development(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()

    assert flask_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert flask_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert flask_app.config["SESSION_COOKIE_SECURE"] is False


def test_create_app_uses_configured_rate_limit_storage(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()

    assert flask_app.config["RATELIMIT_STORAGE_URI"] == "redis://localhost:6379/0"


def test_create_app_requires_persistent_rate_limit_storage_in_production(monkeypatch):
    monkeypatch.delenv("RATELIMIT_STORAGE_URI", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(app_module, "db", FakeDB())

    try:
        app_module.create_app()
    except RuntimeError as exc:
        assert "RATELIMIT_STORAGE_URI" in str(exc)
    else:
        raise AssertionError("production startup should require persistent rate-limit storage")


def test_create_app_uses_testing_config_class(monkeypatch):
    mongo_init_calls = []
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(
        app_module.mongo,
        "init_app",
        lambda flask_app, **kwargs: mongo_init_calls.append(kwargs),
    )
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app(config_class=TestingConfig)

    assert flask_app.config["TESTING"] is True
    assert flask_app.config["SESSION_COOKIE_SECURE"] is False
    assert mongo_init_calls == [
        {
            "serverSelectionTimeoutMS": 5000,
            "connectTimeoutMS": 5000,
            "maxPoolSize": 20,
            "minPoolSize": 0,
        }
    ]


def test_create_app_uses_production_config_class(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app(config_class=ProductionConfig)

    assert flask_app.config["SESSION_COOKIE_SECURE"] is True
    assert flask_app.config["RATELIMIT_STORAGE_URI"] == "redis://localhost:6379/0"


def test_create_app_uses_development_config_class(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app(config_class=DevelopmentConfig)

    assert flask_app.config["SESSION_COOKIE_SECURE"] is False


def test_create_app_allows_mongo_timeout_and_pool_overrides(monkeypatch):
    mongo_init_calls = []

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "1200")
    monkeypatch.setenv("MONGO_CONNECT_TIMEOUT_MS", "2300")
    monkeypatch.setenv("MONGO_MAX_POOL_SIZE", "17")
    monkeypatch.setenv("MONGO_MIN_POOL_SIZE", "3")
    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(
        app_module.mongo,
        "init_app",
        lambda flask_app, **kwargs: mongo_init_calls.append(kwargs),
    )
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()

    assert flask_app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"] == 1200
    assert flask_app.config["MONGO_CONNECT_TIMEOUT_MS"] == 2300
    assert flask_app.config["MONGO_MAX_POOL_SIZE"] == 17
    assert flask_app.config["MONGO_MIN_POOL_SIZE"] == 3
    assert mongo_init_calls == [
        {
            "serverSelectionTimeoutMS": 1200,
            "connectTimeoutMS": 2300,
            "maxPoolSize": 17,
            "minPoolSize": 3,
        }
    ]


def test_create_app_requires_secret_key_outside_testing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(app_module, "db", FakeDB())

    try:
        app_module.create_app()
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("startup should require SECRET_KEY outside testing")


def test_create_app_rejects_insecure_secret_key_defaults(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "supersecretkey")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(app_module, "db", FakeDB())

    try:
        app_module.create_app()
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("startup should reject insecure SECRET_KEY defaults")
