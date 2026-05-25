import werkzeug

import app.web.routes as public_routes
from conftest import build_test_app


if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"


def test_public_profile_route_is_accessible_without_login(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(public_routes,))
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


def test_public_profile_renders_github_repository_showcase(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(public_routes,))
    user_id = test_db.user.insert_one(
        {
            "name": "Public User",
            "profile_photo": "https://example.com/avatar.png",
            "progress": {},
            "external_totals": {},
            "github_username": "saurabhhhcodes",
            "github_repo_list": "saurabhhhcodes/repo-one",
        }
    ).inserted_id

    monkeypatch.setattr(
        public_routes,
        "fetch_github_repo_showcase",
        lambda username, repo_list: [
            {
                "name": "repo-one",
                "url": "https://github.com/saurabhhhcodes/repo-one",
                "description": "Featured repository",
                "language": "Python",
                "stars": 42,
                "forks": 5,
            }
        ],
    )

    with flask_app.test_client() as client:
        response = client.get(f"/u/{user_id}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Featured GitHub Repositories" in html
    assert "repo-one" in html
    assert "Featured repository" in html
    assert "Python" in html
    assert "42" in html
    assert "5" in html


def test_public_profile_invalid_id_returns_400(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(public_routes,))

    with flask_app.test_client() as client:
        response = client.get("/u/not-a-valid-objectid")

    assert response.status_code == 400


def test_public_profile_missing_user_returns_404(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(public_routes,))

    with flask_app.test_client() as client:
        response = client.get("/u/64b64c3f8f1d2b3c4d5e6f70")

    assert response.status_code == 404
