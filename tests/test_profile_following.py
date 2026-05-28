import werkzeug
from bson import ObjectId

import app.web.routes as public_routes
import app.profile.routes as profile_routes
from conftest import build_test_app, login_test_user

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_BASE = {
    "name": "Alice",
    "email": "alice@example.com",
    "progress": {},
    "external_totals": {},
    "is_deactivated": False,
}


def _insert_user(test_db, **overrides):
    doc = {**_USER_BASE, **overrides}
    return test_db.user.insert_one(doc).inserted_id


# ---------------------------------------------------------------------------
# Privacy – public profile page
# ---------------------------------------------------------------------------


def test_private_profile_is_hidden_from_strangers(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes,)
    )
    uid = _insert_user(test_db, is_public=False)

    with flask_app.test_client() as client:
        resp = client.get(f"/u/{uid}")

    assert resp.status_code == 404


def test_private_profile_is_visible_to_owner(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes,)
    )
    uid = _insert_user(test_db, is_public=False)

    with flask_app.test_client() as client:
        login_test_user(client, uid)
        resp = client.get(f"/u/{uid}")

    assert resp.status_code == 200


def test_public_profile_visible_to_everyone(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes,)
    )
    uid = _insert_user(test_db, is_public=True)

    with flask_app.test_client() as client:
        resp = client.get(f"/u/{uid}")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Follow / Unfollow routes
# ---------------------------------------------------------------------------


def test_follow_user_creates_follows_document(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes)
    )
    alice = _insert_user(test_db, name="Alice")
    bob = _insert_user(test_db, name="Bob", is_public=True)

    with flask_app.test_client() as client:
        login_test_user(client, alice)
        resp = client.post(f"/u/{bob}/follow")

    assert resp.status_code == 200
    assert test_db.follows.count_documents(
        {"follower_id": alice, "followed_id": bob}
    ) == 1


def test_follow_is_idempotent(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes)
    )
    alice = _insert_user(test_db, name="Alice")
    bob = _insert_user(test_db, name="Bob", is_public=True)

    with flask_app.test_client() as client:
        login_test_user(client, alice)
        client.post(f"/u/{bob}/follow")
        resp = client.post(f"/u/{bob}/follow")  # second follow – must not error

    assert resp.status_code == 200
    assert test_db.follows.count_documents(
        {"follower_id": alice, "followed_id": bob}
    ) == 1


def test_unfollow_removes_follows_document(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes)
    )
    alice = _insert_user(test_db, name="Alice")
    bob = _insert_user(test_db, name="Bob", is_public=True)
    test_db.follows.insert_one(
        {"follower_id": alice, "followed_id": bob}
    )

    with flask_app.test_client() as client:
        login_test_user(client, alice)
        resp = client.post(f"/u/{bob}/unfollow")

    assert resp.status_code == 200
    assert test_db.follows.count_documents(
        {"follower_id": alice, "followed_id": bob}
    ) == 0


def test_cannot_follow_yourself(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes)
    )
    alice = _insert_user(test_db, name="Alice")

    with flask_app.test_client() as client:
        login_test_user(client, alice)
        resp = client.post(f"/u/{alice}/follow")

    assert resp.status_code == 400


def test_cannot_follow_private_profile(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes)
    )
    alice = _insert_user(test_db, name="Alice")
    bob = _insert_user(test_db, name="Bob", is_public=False)

    with flask_app.test_client() as client:
        login_test_user(client, alice)
        resp = client.post(f"/u/{bob}/follow")

    assert resp.status_code == 403


def test_follow_requires_login(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes)
    )
    bob = _insert_user(test_db, name="Bob", is_public=True)

    with flask_app.test_client() as client:
        resp = client.post(f"/u/{bob}/follow")

    # flask-login redirects unauthenticated requests.
    assert resp.status_code in (302, 401)


# ---------------------------------------------------------------------------
# Privacy – leaderboard filter
# ---------------------------------------------------------------------------


def test_private_users_excluded_from_leaderboard(monkeypatch):
    from app.leaderboard import service as lb_service

    flask_app, test_db = build_test_app(
        monkeypatch, extra_db_targets=(public_routes, profile_routes, lb_service)
    )
    _insert_user(test_db, name="Public Alice", is_public=True)
    _insert_user(test_db, name="Private Bob", is_public=False)

    with flask_app.app_context():
        entries = lb_service.build_leaderboard_data()

    names = [e["name"] for e in entries]
    assert "Public Alice" in names
    assert "Private Bob" not in names
