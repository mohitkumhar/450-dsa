import sys
from unittest.mock import MagicMock

import mongomock
import pytest

import app as app_module
import app.auth.routes as auth_routes

# Pillow (PIL) doesn't support Python 3.14 yet.
# Mock it only when it is unavailable so normal CI can exercise the real
# card generator.
try:
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    PILLOW_AVAILABLE = True
except Exception:
    PILLOW_AVAILABLE = False
    for _mod in ('PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont'):
        sys.modules.setdefault(_mod, MagicMock())
    sys.modules.setdefault('card_generator', MagicMock())


def pytest_collection_modifyitems(config, items):
    if PILLOW_AVAILABLE:
        return

    skip_progress_card = pytest.mark.skip(reason="Pillow is unavailable")
    for item in items:
        if item.nodeid.startswith("tests/test_progress_card.py"):
            item.add_marker(skip_progress_card)


def build_test_app(monkeypatch, *, extra_db_targets=(), oauth_clients=None):
    test_db = mongomock.MongoClient().db
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    for target in (app_module, auth_routes, *extra_db_targets):
        monkeypatch.setattr(target, "db", test_db)

    if oauth_clients:
        for client_name, client in oauth_clients.items():
            monkeypatch.setattr(auth_routes, client_name, client)

    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True
    return flask_app, test_db


def login_test_user(client, user_id):
    if hasattr(user_id, "user"):
        user_id = user_id.user.insert_one(
            {"email": "user@example.com", "progress": {}, "is_admin": False}
        ).inserted_id
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return user_id


def set_csrf_token(client, token="test-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def csrf_headers(client, token="test-csrf-token"):
    return {"X-CSRFToken": set_csrf_token(client, token)}
