from types import SimpleNamespace

from bson import ObjectId

import app.auth.routes as auth_routes


def test_load_user_uses_projection_for_session_loading(monkeypatch):
    user_id = ObjectId()
    captured = {}

    class FakeUserCollection:
        def find_one(self, query, projection=None):
            captured["query"] = query
            captured["projection"] = projection
            return {
                "_id": user_id,
                "name": "Test User",
                "email": "user@example.com",
                "is_admin": False,
                "progress": {},
            }

    monkeypatch.setattr(auth_routes, "db", SimpleNamespace(user=FakeUserCollection()))

    user = auth_routes.load_user(str(user_id))

    assert captured["query"] == {"_id": user_id}
    assert captured["projection"] == auth_routes.USER_SESSION_PROJECTION
    assert user is not None
    assert user.id == user_id
    assert user.name == "Test User"
