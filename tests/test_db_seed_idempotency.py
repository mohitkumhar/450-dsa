import json
from pathlib import Path

import mongomock

import app as app_module
import app.tracker.routes as tracker_routes


def test_first_request_seeding_is_idempotent(monkeypatch):
    test_db = mongomock.MongoClient().db
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(tracker_routes, "db", test_db)
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.add_url_rule("/seed-check", "seed_check", lambda: "ok")
    data = json.loads(Path("data.json").read_text(encoding="utf-8"))
    expected_topics = len(data)
    expected_questions = sum(len(topic["questions"]) for topic in data)

    client = flask_app.test_client()
    first_response = client.get("/seed-check")
    flask_app._db_initialized = False
    second_response = client.get("/seed-check")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert test_db.topic.count_documents({}) == expected_topics
    assert test_db.question.count_documents({}) == expected_questions
