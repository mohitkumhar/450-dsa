from bson import ObjectId

import app as app_module
from app.tracker import routes as tracker_routes


QUESTION_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"


class FakeCollection:
    def __init__(self, document=None):
        self.document = document
        self.indexes = []
        self.last_update = None

    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))
        return None

    def count_documents(self, *args, **kwargs):
        return 1

    def find_one(self, *args, **kwargs):
        return self.document

    def update_one(self, *args, **kwargs):
        self.last_update = (args, kwargs)
        return None


class FakeDB:
    def __init__(self):
        self.user = FakeCollection()
        self.topic = FakeCollection()
        self.question = FakeCollection(
            {
                "_id": ObjectId(QUESTION_ID),
                "problem": "Two Sum",
                "topic": ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb"),
            }
        )


class FakeUser:
    def __init__(self):
        self.id = "user-123"
        self.progress = {}

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    def reload(self):
        return None


def create_test_app(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/450_dsa")
    monkeypatch.setattr(app_module, "db", fake_db)
    monkeypatch.setattr(tracker_routes, "db", fake_db)
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda name, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    return flask_app


def login_session(client):
    with client.session_transaction() as session:
        session["_user_id"] = "user-123"
        session["_fresh"] = True


def post_notes(client, payload):
    return client.post(
        f"/update_question/{QUESTION_ID}",
        json=payload,
        content_type="application/json",
    )


def test_notes_valid_string(monkeypatch):
    flask_app = create_test_app(monkeypatch)
    fake_user = FakeUser()

    monkeypatch.setattr(tracker_routes, "current_user", fake_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: fake_user)

    with flask_app.test_client() as client:
        login_session(client)
        response = post_notes(client, {"notes": "Great problem"})

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_notes_non_string_integer(monkeypatch):
    flask_app = create_test_app(monkeypatch)
    fake_user = FakeUser()

    monkeypatch.setattr(tracker_routes, "current_user", fake_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: fake_user)

    with flask_app.test_client() as client:
        login_session(client)
        response = post_notes(client, {"notes": 12345})

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "notes must be a string"}


def test_notes_non_string_dict(monkeypatch):
    flask_app = create_test_app(monkeypatch)
    fake_user = FakeUser()

    monkeypatch.setattr(tracker_routes, "current_user", fake_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: fake_user)

    with flask_app.test_client() as client:
        login_session(client)
        response = post_notes(client, {"notes": {"key": "val"}})

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "notes must be a string"}


def test_notes_oversized_string(monkeypatch):
    flask_app = create_test_app(monkeypatch)
    fake_user = FakeUser()

    monkeypatch.setattr(tracker_routes, "current_user", fake_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: fake_user)

    with flask_app.test_client() as client:
        login_session(client)
        response = post_notes(client, {"notes": "a" * 1001})

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "notes must be 1000 characters or fewer",
    }
