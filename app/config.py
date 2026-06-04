import os
import secrets
import sys
import warnings


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def current_environment_name():
    for key in ("APP_ENV", "FLASK_ENV", "ENV"):
        value = os.environ.get(key)
        if value:
            return value.strip().lower()
    if env_flag("FLASK_DEBUG"):
        return "development"
    return ""


class BaseConfig:
    SECRET_KEY = None
    MONGO_URI = "mongodb://localhost:27017/450_dsa"
    MONGO_SERVER_SELECTION_TIMEOUT_MS = 5000
    MONGO_CONNECT_TIMEOUT_MS = 5000
    MONGO_MAX_POOL_SIZE = 20
    MONGO_MIN_POOL_SIZE = 0
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300
    SEND_FILE_MAX_AGE_DEFAULT = 86400
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    SWAGGER = {
        "title": "450 DSA Tracker API",
        "uiversion": 3,
    }
    RATELIMIT_STORAGE_URI = "memory://"
    INSECURE_SECRET_KEYS = {
        None,
        "",
        "supersecretkey",
        "supersecretkey-change-me",
        "change-me",
        "change-me-to-a-random-string",
        "dev",
        "your-random-secret-key",
        "replace-this-with-a-real-secret",
    }

    @classmethod
    def apply_environment_overrides(cls, app):
        secret_key = os.environ.get("SECRET_KEY")
        if secret_key is None:
            secret_key = cls.SECRET_KEY
        if isinstance(secret_key, str):
            secret_key = secret_key.strip()
        if not app.config.get("TESTING") and secret_key in cls.INSECURE_SECRET_KEYS:
            warnings.warn(
                "SECRET_KEY is insecure or missing! Using a random temporary key. "
                "User sessions will not persist across restarts.",
                RuntimeWarning,
                stacklevel=2,
            )
            secret_key = secrets.token_hex(32)
        app.config["SECRET_KEY"] = secret_key
        app.config["MONGO_URI"] = os.environ.get("MONGO_URI", cls.MONGO_URI)
        app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"] = env_int(
            "MONGO_SERVER_SELECTION_TIMEOUT_MS",
            cls.MONGO_SERVER_SELECTION_TIMEOUT_MS,
        )
        app.config["MONGO_CONNECT_TIMEOUT_MS"] = env_int(
            "MONGO_CONNECT_TIMEOUT_MS",
            cls.MONGO_CONNECT_TIMEOUT_MS,
        )
        app.config["MONGO_MAX_POOL_SIZE"] = env_int(
            "MONGO_MAX_POOL_SIZE",
            cls.MONGO_MAX_POOL_SIZE,
        )
        app.config["MONGO_MIN_POOL_SIZE"] = env_int(
            "MONGO_MIN_POOL_SIZE",
            cls.MONGO_MIN_POOL_SIZE,
        )
        app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get(
            "SESSION_COOKIE_SAMESITE",
            cls.SESSION_COOKIE_SAMESITE,
        )
        app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
            "RATELIMIT_STORAGE_URI",
            cls.RATELIMIT_STORAGE_URI,
        )


class DevelopmentConfig(BaseConfig):
    SESSION_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-only-secret-not-for-production"
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True

    @classmethod
    def apply_environment_overrides(cls, app):
        secret_key = os.environ.get("SECRET_KEY", "").strip()
        if secret_key in cls.INSECURE_SECRET_KEYS:
            sys.exit(
                "[FATAL] SECRET_KEY must be set to a secure value in production. "
                "Run: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        super().apply_environment_overrides(app)


CONFIG_BY_ENV = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "local": DevelopmentConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}


def resolve_config_class():
    return CONFIG_BY_ENV.get(current_environment_name(), BaseConfig)


# GSSoC Flask CORS Setup Rules
# Allow origin requests only from trusted subdomains.
