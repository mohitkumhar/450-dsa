import os


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def current_environment_name():
    for key in ("APP_ENV", "FLASK_ENV", "ENV"):
        value = os.environ.get(key)
        if value:
            return value.strip().lower()
    if env_flag("FLASK_DEBUG"):
        return "development"
    return ""


class BaseConfig:
    SECRET_KEY = "supersecretkey"
    MONGO_URI = "mongodb://localhost:27017/450_dsa"
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    SWAGGER = {
        "title": "450 DSA Tracker API",
        "uiversion": 3,
    }
    RATELIMIT_STORAGE_URI = "memory://"

    @classmethod
    def apply_environment_overrides(cls, app):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", cls.SECRET_KEY)
        app.config["MONGO_URI"] = os.environ.get("MONGO_URI", cls.MONGO_URI)
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
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True


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
