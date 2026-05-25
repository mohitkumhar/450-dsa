from types import SimpleNamespace

from flask import Flask

import app.profile.routes as profile_routes
from app.profile.routes import profile_bp


def create_profile_test_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True, SECRET_KEY="test-secret")
    app.register_blueprint(profile_bp)
    return app


def test_edit_profile_normalizes_featured_github_repositories(monkeypatch):
    app = create_profile_test_app()
    captured = {}

    monkeypatch.setattr(
        profile_routes,
        "current_user",
        SimpleNamespace(
            id="user-1",
            github_username="saurabhhhcodes",
            reload=lambda: captured.setdefault("reloaded", True),
        ),
    )
    monkeypatch.setattr(profile_routes, "build_profile_updates", lambda data: ({}, None))
    monkeypatch.setattr(
        profile_routes,
        "db",
        SimpleNamespace(
            user=SimpleNamespace(
                update_one=lambda query, update: captured.setdefault("db_update", (query, update))
            )
        ),
    )
    monkeypatch.setattr(
        profile_routes.cache,
        "delete",
        lambda key: captured.setdefault("deleted_cache_key", key),
    )

    response = app.test_client().post(
        "/edit_profile",
        json={
            "github_username": "saurabhhhcodes",
            "github_repo_list": "repo-one\nrepo-two",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert captured["db_update"][1]["$set"]["github_repo_list"] == (
        "saurabhhhcodes/repo-one\nsaurabhhhcodes/repo-two"
    )
    assert captured["deleted_cache_key"] == "card_user-1"
    assert captured["reloaded"] is True


def test_edit_profile_rejects_invalid_featured_github_repository(monkeypatch):
    app = create_profile_test_app()

    monkeypatch.setattr(
        profile_routes,
        "current_user",
        SimpleNamespace(
            id="user-1",
            github_username="saurabhhhcodes",
            reload=lambda: None,
        ),
    )
    monkeypatch.setattr(profile_routes, "build_profile_updates", lambda data: ({}, None))

    response = app.test_client().post(
        "/edit_profile",
        json={
            "github_username": "saurabhhhcodes",
            "github_repo_list": "bad slug!",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "GitHub repositories must use owner/repo format with valid characters.",
    }


def test_edit_profile_tolerates_cache_delete_failures(monkeypatch):
    app = create_profile_test_app()
    captured = {}

    monkeypatch.setattr(
        profile_routes,
        "current_user",
        SimpleNamespace(
            id="user-1",
            github_username="saurabhhhcodes",
            reload=lambda: captured.setdefault("reloaded", True),
        ),
    )
    monkeypatch.setattr(profile_routes, "build_profile_updates", lambda data: ({}, None))
    monkeypatch.setattr(
        profile_routes,
        "db",
        SimpleNamespace(
            user=SimpleNamespace(
                update_one=lambda query, update: captured.setdefault("db_update", (query, update))
            )
        ),
    )
    monkeypatch.setattr(
        profile_routes.cache,
        "delete",
        lambda key: (_ for _ in ()).throw(RuntimeError("cache unavailable")),
    )

    response = app.test_client().post(
        "/edit_profile",
        json={
            "github_username": "saurabhhhcodes",
            "github_repo_list": "repo-one",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert captured["db_update"][1]["$set"]["github_repo_list"] == "saurabhhhcodes/repo-one"
    assert captured["reloaded"] is True
