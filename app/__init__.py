import json
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flasgger import Swagger
from flask import Flask, session

from app.admin import admin_bp
from app.auth import auth_bp
from app.faq import faq_bp
from app.extensions import bcrypt, db, limiter, login_manager, mongo, oauth, cache
from app.leaderboard import leaderboard_bp
from app.web.routes import public_bp
from app.profile import profile_bp
from app.security import build_content_security_policy
from app.search import search_bp
from app.tracker import tracker_bp
from app.utils import platform_color_filter, platform_name_filter


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_local_environment():
    app_env = os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or os.environ.get("ENV") or ""
    return app_env.strip().lower() in {"development", "dev", "local", "test", "testing"} or _env_flag("FLASK_DEBUG")


def _is_production_environment():
    return os.environ.get("FLASK_ENV") == "production" or os.environ.get("APP_ENV") == "production"


def _configure_rate_limit_storage(app):
    storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    if storage_uri == "memory://" and _is_production_environment():
        raise RuntimeError("Set RATELIMIT_STORAGE_URI to a persistent backend before running in production.")
    app.config["RATELIMIT_STORAGE_URI"] = storage_uri


def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")
    app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/450_dsa")
    _configure_rate_limit_storage(app)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["SESSION_COOKIE_SECURE"] = _env_flag("SESSION_COOKIE_SECURE", default=not _is_local_environment())
    app.config["CACHE_TYPE"] = "SimpleCache"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 300
    app.config["SWAGGER"] = {
        "title": "450 DSA Tracker API",
        "uiversion": 3,
    }
    
    cache.init_app(app)
    Swagger(
        app,
        template={
            "swagger": "2.0",
            "info": {
                "title": "450 DSA Tracker API",
                "description": "API documentation for search, leaderboard, progress, and profile endpoints.",
                "version": "1.0.0",
            },
            "basePath": "/",
            "securityDefinitions": {
                "SessionAuth": {
                    "type": "apiKey",
                    "name": "session",
                    "in": "cookie",
                    "description": "Flask-Login session cookie.",
                },
            },
        },
    )

    mongo.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    oauth.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"

    oauth.register(
        name="github",
        client_id=os.environ.get("GITHUB_CLIENT_ID", "your-github-client-id"),
        client_secret=os.environ.get("GITHUB_CLIENT_SECRET", "your-github-client-secret"),
        access_token_url="https://github.com/login/oauth/access_token",
        access_token_params=None,
        authorize_url="https://github.com/login/oauth/authorize",
        authorize_params=None,
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )

    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID", "your-google-client-id"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "your-google-client-secret"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    try:
        db.user.create_index("email", unique=True, sparse=True)
        db.user.create_index("github_id", unique=True, sparse=True)
        db.user.create_index("google_id", unique=True, sparse=True)
        db.user.create_index("is_admin")
        db.topic.create_index("name", unique=True)
        db.question.create_index([("problem", "text")], name="problem_text")
    except Exception:
        pass

    # Lightweight schema backfill for legacy user documents.
    db.user.update_many({"is_admin": {"$exists": False}}, {"$set": {"is_admin": False}})

    data_path = Path(app.root_path).parent / "data.json"
    app._db_initialized = False

    def init_db():
        if db.topic.count_documents({}) == 0:
            with data_path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            for topic in data:
                result = db.topic.insert_one({"name": topic["topicName"], "position": topic["position"]})
                topic_id = result.inserted_id
                questions = []
                for question in topic["questions"]:
                    difficulty = question.get("difficulty", "Medium")
                    questions.append(
                        {
                            "topic": topic_id,
                            "problem": question["Problem"],
                            "url": question["URL"],
                            "url2": question.get("URL2", ""),
                            "difficulty": difficulty,
                        }
                    )
                if questions:
                    db.question.insert_many(questions)

    @app.before_request
    def ensure_db_initialized():
        if not app._db_initialized:
            init_db()
            app._db_initialized = True

    app.add_template_filter(platform_name_filter, "platform_name")
    app.add_template_filter(platform_color_filter, "platform_color")

    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            token = session.get("csrf_token")
            if not token:
                token = secrets.token_urlsafe(32)
                session["csrf_token"] = token
            return token

        return {"csrf_token": csrf_token}

    app.register_blueprint(auth_bp)
    app.register_blueprint(faq_bp)  
    app.register_blueprint(tracker_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        retry_after = getattr(e, 'retry_after', 60)
        from flask import jsonify
        response = jsonify({
            'error': 'Too many requests',
            'message': str(e.description),
            'retry_after': retry_after
        })
        response.status_code = 429
        response.headers['Retry-After'] = str(retry_after)
        return response

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = build_content_security_policy()
        return response



    return app
