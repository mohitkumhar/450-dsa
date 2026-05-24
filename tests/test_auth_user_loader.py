from bson import ObjectId

import app.auth.routes as auth_routes


class RecordingUserCollection:
    def __init__(self, document):
        self.document = document
        self.calls = []

    def find_one(self, query, projection=None):
        self.calls.append((query, projection))
        if query.get("_id") == self.document["_id"]:
            return dict(self.document)
        return None


class RecordingDB:
    def __init__(self, document):
        self.user = RecordingUserCollection(document)


def test_load_user_uses_lightweight_projection(monkeypatch):
    user_id = ObjectId()
    db = RecordingDB(
        {
            "_id": user_id,
            "name": "Loader Test",
            "email": "loader@example.com",
            "progress": {"q1": {"done": True}},
            "is_admin": True,
            "leetcode_username": "leet",
        }
    )
    monkeypatch.setattr(auth_routes, "db", db)

    user = auth_routes.load_user(str(user_id))

    assert user is not None
    assert str(user.get_id()) == str(user_id)
    assert user.name == "Loader Test"
    assert user.email == "loader@example.com"
    assert user.progress == {"q1": {"done": True}}
    assert user.is_admin is True
    assert user.leetcode_username == "leet"
    assert db.user.calls == [
        ({"_id": user_id}, auth_routes.SESSION_USER_PROJECTION),
    ]


def test_load_user_returns_none_for_invalid_id():
    assert auth_routes.load_user("not-a-valid-objectid") is None
