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
from app.extensions import bcrypt, cache, db, limiter, login_manager, mongo, oauth, mail
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
from app.practice.routes import practice_bp
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
    mail.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    oauth.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"

    oauth.register(
        name="github",
        client_id=os.environ.get("GITHUB_CLIENT_ID"),
        client_secret=os.environ.get("GITHUB_CLIENT_SECRET"),
        access_token_url="https://github.com/login/oauth/access_token",
        access_token_params=None,
        authorize_url="https://github.com/login/oauth/authorize",
        authorize_params=None,
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )

    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    try:
        # ---- user ----
        db.user.create_index("email",     unique=True, sparse=True)
        db.user.create_index("github_id", unique=True, sparse=True)
        db.user.create_index("google_id", unique=True, sparse=True)
        db.user.create_index("is_admin")

        # ---- topic ----
        db.topic.create_index("name",     unique=True)
        db.topic.create_index("position")

        # ---- question (new + legacy) ----
        # sparse=True: documents without questionId (null) are excluded from
        # the unique constraint, so legacy docs that haven't been assigned an
        # ID yet don't collide with each other.
        try:
            db.question.create_index("questionId", unique=True, sparse=True)
        except Exception:
            # Old non-sparse index exists — drop and recreate as sparse (one-time migration)
            try:
                db.question.drop_index("questionId_1")
            except Exception:
                pass
            db.question.create_index("questionId", unique=True, sparse=True)
        db.question.create_index("titleSlug",   unique=True)
        db.question.create_index("topic")
        db.question.create_index("difficulty")
        db.question.create_index("topics")        # multikey
        db.question.create_index("companies")     # multikey
        db.question.create_index("status")
        db.question.create_index([("title", "text")], name="title_text")
        # Legacy compound for tracker routes — keep existing data compatible
        try:
            db.question.create_index(
                [("topic", 1), ("problem", 1), ("url", 1)],
                unique=True, name="topic_problem_url", sparse=True
            )
        except Exception:
            _dedupe_seeded_questions()
            db.question.create_index(
                [("topic", 1), ("problem", 1), ("url", 1)],
                unique=True, name="topic_problem_url", sparse=True
            )

        # ---- sheet ----
        db.sheet.create_index("sheetId", unique=True)
        db.sheet.create_index("name")

        # ---- user_sheet_progress ----
        db.user_sheet_progress.create_index(
            [("userId", 1), ("sheetId", 1), ("questionId", 1)],
            unique=True, name="userId_sheetId_questionId"
        )
        db.user_sheet_progress.create_index("userId")
        db.user_sheet_progress.create_index("sheetId")
        db.user_sheet_progress.create_index("questionId")
        db.user_sheet_progress.create_index("status")
        db.user_sheet_progress.create_index([("updatedAt", -1)])

        # ---- submissions ----
        db.submissions.create_index("user_id")
        db.submissions.create_index("q_id")
        db.submissions.create_index([("user_id", 1), ("q_id", 1)], name="user_id_q_id")
        db.submissions.create_index("status")
        db.submissions.create_index([("timestamp", -1)])
        db.submissions.create_index("language")

        # ---- cohort ----
        db.cohort.create_index("join_code",  unique=True)
        db.cohort.create_index("created_by")

        # ---- cohort_membership ----
        db.cohort_membership.create_index(
            [("cohort_id", 1), ("user_id", 1)], unique=True, name="cohort_id_user_id"
        )
        db.cohort_membership.create_index("user_id")

        # ---- Schema backfill for legacy documents ----
        db.user.update_many({"is_admin":              {"$exists": False}}, {"$set": {"is_admin": False}})
        db.user.update_many({"external_totals":       {"$exists": False}}, {"$set": {"external_totals": {}}})
        db.user.update_many({"external_daily_counts": {"$exists": False}}, {"$set": {"external_daily_counts": {}}})
        db.user.update_many({"platform_calendars":    {"$exists": False}}, {"$set": {"platform_calendars": {}}})
        db.user.update_many({"in_sheet_platform_counts": {"$exists": False}}, {"$set": {"in_sheet_platform_counts": {
            "LeetCode": 0, "GFG": 0, "Coding Ninjas": 0,
            "HackerRank": 0, "AtCoder": 0, "Codewars": 0, "Other": 0
        }}})
        db.question.update_many({"companies":       {"$exists": False}}, {"$set": {"companies": []}})
        db.question.update_many({"topics":          {"$exists": False}}, {"$set": {"topics": []}})
        db.question.update_many({"examples":        {"$exists": False}}, {"$set": {"examples": []}})
        db.question.update_many({"constraints":     {"$exists": False}}, {"$set": {"constraints": []}})
        db.question.update_many({"similarQuestions":{"$exists": False}}, {"$set": {"similarQuestions": []}})
        db.question.update_many({"hints":           {"$exists": False}}, {"$set": {"hints": []}})
        db.question.update_many({"editorial_links": {"$exists": False}}, {"$set": {"editorial_links": []}})
        db.question.update_many({"status":          {"$exists": False}}, {"$set": {"status": "published"}})
        db.user_sheet_progress.update_many({"revision_status": {"$exists": False}}, {"$set": {"revision_status": "To Review"}})
        db.user_sheet_progress.update_many({"bookmarked":       {"$exists": False}}, {"$set": {"bookmarked": False}})
    except Exception as exc:
        app.logger.warning(f"Database indexing or schema backfill failed: {exc}")

    data_path = Path(app.root_path).parent / "data.json"
    app._db_initialized = False

    def init_db():
        from datetime import datetime, timezone as _tz
        import re
        with data_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)

        def _slug(text):
            text = text.lower()
            text = re.sub(r'[^a-z0-9]+', '-', text)
            return text.strip('-')

        if not all(hasattr(collection, "bulk_write") for collection in (db.topic, db.question)):
            if db.topic.count_documents({}) == 0:
                for topic in data:
                    result = db.topic.insert_one({
                        "name": topic["topicName"],
                        "position": topic["position"],
                        "started": False,
                        "doneQuestions": 0,
                    })
                    topic_id = result.inserted_id
                    questions = []
                    for idx, question in enumerate(topic["questions"], start=1):
                        difficulty = question.get("difficulty", "Medium")
                        title = question["Problem"]
                        q_data = {
                            # New schema fields
                            "questionId": idx,
                            "titleSlug": _slug(title),
                            "title": title,
                            "content": "",
                            "difficulty": difficulty,
                            "topics": [topic["topicName"]],
                            "companies": [],
                            "examples": [],
                            "constraints": [],
                            "similarQuestions": [],
                            "stats": {
                                "totalAccepted": 0,
                                "totalSubmissions": 0,
                                "acceptanceRate": 0.0,
                                "likes": 0,
                                "dislikes": 0,
                            },
                            "status": "published",
                            "createdAt": datetime.now(_tz.utc),
                            "updatedAt": datetime.now(_tz.utc),
                            # Legacy fields for tracker compatibility
                            "topic": topic_id,
                            "problem": title,
                            "url": question["URL"],
                            "url2": question.get("URL2", ""),
                            "editorial_links": question_editorial_links(question),
                            "hints": question.get("hints", []),
                        }
                        questions.append(q_data)
                    if questions:
                        db.question.insert_many(questions)
            return

        from pymongo import UpdateOne
        topic_updates = []
        for topic in data:
            topic_updates.append(
                UpdateOne(
                    {"name": topic["topicName"]},
                    {"$set": {
                        "position": topic["position"],
                        "started": False,
                        "doneQuestions": 0,
                    }},
                    upsert=True,
                )
            )
        if topic_updates:
            db.topic.bulk_write(topic_updates)

        topic_docs = {doc["name"]: doc["_id"] for doc in db.topic.find({}, {"name": 1})}

        question_updates = []
        # ----------------------------------------------------------------
        # Pre-load ALL existing slugs so we can de-duplicate at build time.
        # This prevents $setOnInsert from ever producing a slug that collides
        # with an already-stored document or with another operation in the
        # same batch (data.json has a handful of title duplicates).
        # ----------------------------------------------------------------
        _used_slugs: set[str] = {
            d["titleSlug"]
            for d in db.question.find(
                {"titleSlug": {"$exists": True}}, {"titleSlug": 1, "_id": 0}
            )
            if d.get("titleSlug")
        }

        def _unique_slug(base: str) -> str:
            """Return base slug if unused, otherwise base-2, base-3 …"""
            candidate = base
            suffix = 2
            while candidate in _used_slugs:
                candidate = f"{base}-{suffix}"
                suffix += 1
            _used_slugs.add(candidate)
            return candidate

        # Global question counter — start after the highest existing questionId
        _max_id_doc = db.question.find_one(
            {"questionId": {"$exists": True, "$type": "number"}},
            {"questionId": 1},
            sort=[("questionId", -1)],
        )
        _next_q_id = (_max_id_doc["questionId"] + 1) if _max_id_doc else 1

        for topic in data:
            topic_id = topic_docs.get(topic["topicName"])
            if not topic_id:
                continue

            for question in topic["questions"]:
                difficulty = question.get("difficulty", "Medium")
                title = question["Problem"]
                # NOTE: titleSlug + questionId are in $setOnInsert only.
                # They are written once on first insert and never touched again.
                # Putting them in $set causes E11000 on re-seeding because the
                # unique indexes reject writing the same value onto a second doc.
                set_fields = {
                    "title": title,
                    "difficulty": difficulty,
                    "topics": [topic["topicName"]],
                    "status": "published",
                    # Legacy fields
                    "url2": question.get("URL2", ""),
                    "editorial_links": question_editorial_links(question),
                    "hints": question.get("hints", []),
                }
                # Only written on first insert — never overwrites enriched data
                set_on_insert = {
                    "questionId": _next_q_id,
                    "titleSlug": _unique_slug(_slug(title)),  # collision-safe
                    "content": "",
                    "companies": [],
                    "examples": [],
                    "constraints": [],
                    "similarQuestions": [],
                    "stats": {
                        "totalAccepted": 0,
                        "totalSubmissions": 0,
                        "acceptanceRate": 0.0,
                        "likes": 0,
                        "dislikes": 0,
                    },
                }
                _next_q_id += 1  # always increment to avoid gaps
                question_updates.append(
                    UpdateOne(
                        {
                            "topic": topic_id,
                            "url": question["URL"],
                        },
                        {
                            "$set": set_fields,
                            "$setOnInsert": set_on_insert,
                        },
                        upsert=True,
                    )
                )

        if question_updates:
            from pymongo.errors import BulkWriteError as _BWE
            try:
                # ordered=False: don't abort the whole batch on a single
                # collision — the remaining operations still execute.
                db.question.bulk_write(question_updates, ordered=False)
            except _BWE as bwe:
                # Log individual failures as warnings; don't crash the app.
                failed = len(bwe.details.get("writeErrors", []))
                ok = len(question_updates) - failed
                app.logger.warning(
                    f"Question seeding: {ok} OK, {failed} skipped "
                    f"(duplicate slug/id conflicts in data.json)"
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
            tid = str(q.get("topic", ""))
            if tid:
                topic_question_count.setdefault(tid, []).append(qid)
            difficulty_map[qid] = q.get("difficulty", "Medium")
            all_questions_pc.append({
                "_id": qid,
                "topic": tid,
                "problem": q.get("problem", q.get("title", "")),
                "url": q.get("url", ""),
                "url2": q.get("url2", ""),
                "difficulty": q.get("difficulty", "Medium"),
                "editorial_links": q.get("editorial_links", []),
                "marks": q.get("marks", 0),
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
            # init_db()  # Disabled: Prevents auto-repopulating 450 questions from data.json
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
    app.register_blueprint(practice_bp)
    from app.sheet.routes import sheet_bp
    app.register_blueprint(sheet_bp)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        retry_after = getattr(e, 'retry_after', None)
        if retry_after in (None, "", "None"):
            retry_after = 60
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


# GSSoC Flask Global Error Handler registration
# Catch 404, 500, and rate-limit HTTP exceptions cleanly.
