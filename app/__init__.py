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
from app.search import search_bp
from app.tracker import tracker_bp
from app.utils import platform_color_filter, platform_name_filter


def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")
    app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/450_dsa")
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

    # Initialize extensions
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

    # Create indexes (skip if using mock)
    try:
        db.user.create_index("email", unique=True, sparse=True)
        db.user.create_index("github_id", unique=True, sparse=True)
        db.user.create_index("google_id", unique=True, sparse=True)
        db.user.create_index("is_admin")
        db.topic.create_index("name", unique=True)
        db.question.create_index([("problem", "text")], name="problem_text")
    except Exception:
        pass  # Skip indexes if using mock DB

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
                    # ADDED: difficulty field
                    difficulty = question.get("difficulty", "Medium")
                    questions.append(
                        {
                            "topic": topic_id,
                            "problem": question["Problem"],
                            "url": question["URL"],
                            "url2": question.get("URL2", ""),
                            "difficulty": difficulty,  # <-- NEW FIELD
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
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "img-src 'self' data: https:;"
        )
        return response



    return app
