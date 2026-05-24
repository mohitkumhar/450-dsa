import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

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


# ---------------------------------------------------------------------------
# Shared test-app factory fixtures — see issue #425
# ---------------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch):
    """Create a Flask test app backed by mongomock with stubbed extensions.

    Patches the module-level ``db`` reference and stubs ``init_app`` on all
    Flask extensions (mongo, bcrypt, login_manager, oauth, limiter, cache)
    so ``create_app()`` does not touch a real server.  Individual test
    modules that import route modules (e.g. ``app.tracker.routes``) must
    also patch their local ``db`` attribute — see the :func:`db` fixture.
    """
    import mongomock

    import app as app_module

    test_db = mongomock.MongoClient().db

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda name, **kwargs: None)
    monkeypatch.setattr(app_module.limiter, "init_app", lambda flask_app: None)
    monkeypatch.setattr(app_module.cache, "init_app", lambda flask_app: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True

    return flask_app


@pytest.fixture
def db(app) -> Any:
    """Return the mongomock database instance patched into ``app_module.db``."""
    import app as app_module

    return app_module.db


@pytest.fixture
def client(app):
    """Test client for the app created by the :func:`app` fixture."""
    return app.test_client()


@pytest.fixture
def logged_in_user(client, db):
    """Insert a plain (non-admin) user into the database and log them in.

    Returns the ``ObjectId`` of the created user.
    """
    from bson import ObjectId

    user_id = db.user.insert_one(
        {"email": "fixture@example.com", "progress": {}, "is_admin": False}
    ).inserted_id
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return user_id
