from types import SimpleNamespace

import app as app_module
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

    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
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
    assert login_manager.login_view == "auth.login"
    assert registered_clients == ["github", "google"]
    assert {"auth", "tracker", "profile", "leaderboard", "search", "admin"} <= set(flask_app.blueprints)

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
    assert "/search" in routes
    assert "/api/search_questions" in routes

    question_indexes = app_module.db.question.indexes
    assert (([("problem", "text")],), {"name": "problem_text"}) in question_indexes
    assert "/admin" in routes
    assert "/admin/users/<user_id>/delete" in routes
