import json
import os
import secrets
from pathlib import Path

from app.config import resolve_config_class, env_flag, ProductionConfig
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


def _configure_rate_limit_storage(app, config_class):
    storage_uri = app.config["RATELIMIT_STORAGE_URI"]
    if storage_uri == "memory://" and config_class is ProductionConfig:
        raise RuntimeError("Set RATELIMIT_STORAGE_URI to a persistent backend before running in production.")


def _mongo_client_options(app):
    return {
        "serverSelectionTimeoutMS": app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"],
        "connectTimeoutMS": app.config["MONGO_CONNECT_TIMEOUT_MS"],
        "maxPoolSize": app.config["MONGO_MAX_POOL_SIZE"],
        "minPoolSize": app.config["MONGO_MIN_POOL_SIZE"],
    }


def create_app(config_class=None):
    load_dotenv()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    config_class = config_class or resolve_config_class()
    app.config.from_object(config_class)
    # Non-test environments must provide a real SECRET_KEY before the app boots.
    config_class.apply_environment_overrides(app)
    _configure_rate_limit_storage(app, config_class)
    app.config["SESSION_COOKIE_SECURE"] = env_flag(
        "SESSION_COOKIE_SECURE",
        default=app.config["SESSION_COOKIE_SECURE"],
    )
    
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

    mongo.init_app(app, **_mongo_client_options(app))
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
        db.topic.create_index("position")
        db.question.create_index("topic")
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

    @app.route("/service-worker.js")
    def service_worker():
        response = app.send_static_file("js/service-worker.js")
        response.mimetype = "application/javascript"
        return response

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
