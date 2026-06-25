from bson import ObjectId

import app.leaderboard.service as leaderboard_service
from tests.conftest import build_test_app, login_test_user


def test_compare_requires_authentication(monkeypatch):
    app, _ = build_test_app(monkeypatch, extra_db_targets=(leaderboard_service,))

    with app.test_client() as client:
        response = client.get(f"/leaderboard/compare/{ObjectId()}")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_compare_renders_current_and_other_user(monkeypatch):
    app, test_db = build_test_app(monkeypatch, extra_db_targets=(leaderboard_service,))

    current_user_id = test_db.user.insert_one(
        {
            "name": "Current User",
            "email": "current@example.com",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {},
            "external_daily_counts": {},
        }
    ).inserted_id
    other_user_id = test_db.user.insert_one(
        {
            "name": "Other User",
            "email": "other@example.com",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {},
            "external_daily_counts": {},
        }
    ).inserted_id

    with app.test_client() as client:
        login_test_user(client, current_user_id)
        response = client.get(f"/leaderboard/compare/{other_user_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Head-to-head comparison" in html
    assert "Current User" in html
    assert "Other User" in html


def test_compare_returns_404_for_unknown_user(monkeypatch):
    app, test_db = build_test_app(monkeypatch, extra_db_targets=(leaderboard_service,))

    current_user_id = test_db.user.insert_one(
        {
            "name": "Current User",
            "email": "current@example.com",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {},
            "external_daily_counts": {},
        }
    ).inserted_id

    with app.test_client() as client:
        login_test_user(client, current_user_id)
        response = client.get(f"/leaderboard/compare/{ObjectId()}")

    assert response.status_code == 404
    assert "User not found on the leaderboard." in response.get_data(as_text=True)
