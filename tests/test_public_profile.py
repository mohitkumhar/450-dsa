import mongomock
import werkzeug

import app as app_module
import app.auth.routes as auth_routes
import app.web.routes as public_routes


if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"


def create_test_app(monkeypatch):
    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(auth_routes, "db", test_db)
    monkeypatch.setattr(public_routes, "db", test_db)

    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True

    return flask_app, test_db


def test_public_profile_route_is_accessible_without_login(monkeypatch):
    flask_app, test_db = create_test_app(monkeypatch)
    user_id = test_db.user.insert_one(
        {
            "name": "Public User",
            "email": "private@example.com",
            "notes": "internal only",
            "profile_photo": "https://example.com/avatar.png",
            "progress": {},
            "external_totals": {
                "LeetCode": 12,
                "LeetCode_Easy": 3,
                "LeetCode_Medium": 6,
                "LeetCode_Hard": 3,
                "LeetCode_Rating": 1500,
                "GFG": 4,
                "HackerRank": 2,
                "Coding Ninjas": 1,
            },
        }
    ).inserted_id

    with flask_app.test_client() as client:
        response = client.get(f"/u/{user_id}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Public User" in html
    assert "private@example.com" not in html
    assert "internal only" not in html
    assert "og:title" in html
    assert "og:description" in html
    assert "This is a public profile page." in html


def test_public_profile_invalid_id_returns_400(monkeypatch):
    flask_app, _ = create_test_app(monkeypatch)

    with flask_app.test_client() as client:
        response = client.get("/u/not-a-valid-objectid")

    assert response.status_code == 400


def test_public_profile_missing_user_returns_404(monkeypatch):
    flask_app, _ = create_test_app(monkeypatch)

    with flask_app.test_client() as client:
        response = client.get("/u/64b64c3f8f1d2b3c4d5e6f70")

    assert response.status_code == 404
