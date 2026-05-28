import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.config import resolve_config_class, env_flag, ProductionConfig
from dotenv import load_dotenv
from flasgger import Swagger
from flask import Flask, abort, g, jsonify, request

from app.admin import admin_bp
from app.auth import auth_bp
from app.faq import faq_bp
from app.extensions import bcrypt, cache, db, limiter, login_manager, mongo, oauth
from app.leaderboard import leaderboard_bp
from app.web.routes import public_bp
from app.profile import profile_bp
from app.security import (
    CSRF_PROTECTED_METHODS,
    build_content_security_policy,
    csrf_token,
    validate_csrf_request,
)
from app.search import search_bp
from app.tracker import tracker_bp
from app.cohort.routes import cohort_bp
from app.utils import (
    platform_color_filter,
    platform_name_filter,
    platform_profile_url,
    question_editorial_links,
    safe_url_filter,
)


ROUTE_TIMING_ENDPOINTS = {
    "profile.profile",
    "profile.sync_platforms",
    "leaderboard.leaderboard",
    "leaderboard.api_leaderboard",
    "search.search",
    "search.api_search_questions",
    "tracker.export_csv",
    "tracker.export_notes",
}


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


def _dedupe_seeded_questions():
    if not all(hasattr(db.question, attr) for attr in ("aggregate", "delete_many")):
        return

    duplicate_groups = db.question.aggregate(
        [
            {
                "$group": {
                    "_id": {
                        "topic": "$topic",
                        "problem": "$problem",
                        "url": "$url",
                    },
                    "ids": {"$push": "$_id"},
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]
    )
    for group in duplicate_groups:
        duplicate_ids = group["ids"][1:]
        if duplicate_ids:
            db.question.delete_many({"_id": {"$in": duplicate_ids}})


def create_app(config_class=None):
    load_dotenv()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    config_class = config_class or resolve_config_class()
    app.config.from_object(config_class)
    # Non-test environments without a real SECRET_KEY use a temporary fallback.
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
        _dedupe_seeded_questions()
        db.question.create_index([("topic", 1), ("problem", 1), ("url", 1)], unique=True)
        db.question.create_index([("problem", "text")], name="problem_text")
        db.cohort.create_index("join_code", unique=True)
        db.cohort_membership.create_index([("cohort_id", 1), ("user_id", 1)], unique=True)
        db.cohort_membership.create_index("user_id")
        
        # Lightweight schema backfill for legacy user documents.
        db.user.update_many({"is_admin": {"$exists": False}}, {"$set": {"is_admin": False}})
    except Exception as exc:
        app.logger.warning(f"Database indexing or schema backfill failed: {exc}")
    data_path = Path(app.root_path).parent / "data.json"
    app._db_initialized = False

    def init_db():
        with data_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        if not all(hasattr(collection, "update_one") for collection in (db.topic, db.question)):
            if db.topic.count_documents({}) == 0:
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
                                "editorial_links": question_editorial_links(question),
                                "difficulty": difficulty,
                            }
                        )
                    if questions:
                        db.question.insert_many(questions)
            return

        for topic in data:
            db.topic.update_one(
                {"name": topic["topicName"]},
                {"$set": {"position": topic["position"]}},
                upsert=True,
            )
            topic_doc = db.topic.find_one({"name": topic["topicName"]})
            if not topic_doc:
                continue

            topic_id = topic_doc["_id"]
            for question in topic["questions"]:
                difficulty = question.get("difficulty", "Medium")
                db.question.update_one(
                    {
                        "topic": topic_id,
                        "problem": question["Problem"],
                        "url": question["URL"],
                    },
                    {
                        "$set": {
                            "url2": question.get("URL2", ""),
                            "editorial_links": question_editorial_links(question),
                            "difficulty": difficulty,
                        }
                    },
                    upsert=True,
                )

    def _precompute_static_data(app):
        """Precompute static question/topic metadata and store in app config."""
        try:
            questions = list(db.question.find())
            topics = list(db.topic.find().sort("position", 1))
        except Exception:
            return

        topic_question_count = {}
        difficulty_map = {}
        all_questions_pc = []
        topic_lookup = {}

        for t in topics:
            tid = str(t["_id"])
            topic_lookup[tid] = {"name": t["name"], "position": t["position"]}

        for q in questions:
            qid = str(q["_id"])
            tid = str(q["topic"])
            topic_question_count.setdefault(tid, []).append(qid)
            difficulty_map[qid] = q.get("difficulty", "Medium")
            all_questions_pc.append({
                "_id": qid,
                "topic": tid,
                "problem": q.get("problem", ""),
                "url": q.get("url", ""),
                "url2": q.get("url2", ""),
                "difficulty": q.get("difficulty", "Medium"),
                "editorial_links": q.get("editorial_links", []),
            })

        topics_pc = [
            {"_id": str(t["_id"]), "name": t["name"], "position": t["position"]}
            for t in topics
        ]

        app.config["_PRECOMPUTED"] = {
            "all_questions": all_questions_pc,
            "topics": topics_pc,
            "topic_lookup": topic_lookup,
            "topic_question_count": topic_question_count,
            "difficulty_map": difficulty_map,
            "total_questions": len(questions),
        }

    @app.before_request
    def ensure_db_initialized():
        if request.endpoint == "health_check":
            return None

        if not app._db_initialized:
            init_db()
            _precompute_static_data(app)
            app._db_initialized = True

    from app.platforms.metadata import PLATFORM_META

    @app.template_filter("platform_badge")
    def platform_badge_filter(name):
        meta = PLATFORM_META.get(name)
        if meta:
            return meta["badge_class"]
        return "badge-link"

    @app.context_processor
    def inject_platform_metadata():
        return {"PLATFORM_META": PLATFORM_META}

    @app.before_request
    def start_route_timer():
        if request.endpoint in ROUTE_TIMING_ENDPOINTS:
            g.route_timer_start = perf_counter()

    @app.before_request
    def protect_unsafe_requests():
        if request.method not in CSRF_PROTECTED_METHODS:
            return None

        if validate_csrf_request():
            return None

        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "Invalid CSRF token."}), 403

        abort(403)

    app.add_template_filter(platform_name_filter, "platform_name")
    app.add_template_filter(platform_color_filter, "platform_color")
    app.add_template_filter(platform_profile_url, "platform_url")
    app.add_template_filter(safe_url_filter, "safe_url")

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": csrf_token}

    @app.get("/health")
    def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

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
    app.register_blueprint(cohort_bp)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        retry_after = getattr(e, 'retry_after', 60)
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
        started_at = getattr(g, "route_timer_start", None)
        if started_at is not None and request.endpoint in ROUTE_TIMING_ENDPOINTS:
            app.logger.info(
                "route_timing %s",
                json.dumps(
                    {
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "route": request.url_rule.rule if request.url_rule else request.path,
                        "status_code": response.status_code,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                    sort_keys=True,
                ),
            )
        response.headers["Content-Security-Policy"] = build_content_security_policy()
        return response



    return app
