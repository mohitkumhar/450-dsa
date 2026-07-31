import app.leaderboard.routes as leaderboard_routes
from conftest import build_test_app


def _build_entries(count):
    return [
        {
            "user_id": str(index),
            "name": f"User {index}",
            "profile_photo": "",
            "college": "Test College",
            "c_score": count - index,
            "total_solved": count - index,
            "dsa_done": index,
            "lc_total": index,
            "lc_rating": count - index,
        }
        for index in range(count)
    ]


def _patch_leaderboard_data(monkeypatch, entries):
    monkeypatch.setattr(
        leaderboard_routes,
        "build_leaderboard_data",
        lambda: [entry.copy() for entry in entries],
    )


def test_api_leaderboard_defaults_invalid_pagination_values(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)
    _patch_leaderboard_data(monkeypatch, _build_entries(30))

    response = flask_app.test_client().get("/api/leaderboard?page=abc&per_page=bad")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 1
    assert payload["per_page"] == 20
    assert payload["total"] == 30
    assert payload["total_pages"] == 2
    assert len(payload["entries"]) == 20


def test_api_leaderboard_clamps_negative_and_zero_pagination_values(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)
    _patch_leaderboard_data(monkeypatch, _build_entries(5))

    response = flask_app.test_client().get("/api/leaderboard?page=-3&per_page=0")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 1
    assert payload["per_page"] == 1
    assert payload["total"] == 5
    assert payload["total_pages"] == 5
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["rank"] == 1


def test_api_leaderboard_caps_oversized_per_page(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)
    _patch_leaderboard_data(monkeypatch, _build_entries(120))

    response = flask_app.test_client().get("/api/leaderboard?page=2&per_page=150")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 2
    assert payload["per_page"] == 100
    assert payload["total"] == 120
    assert payload["total_pages"] == 2
    assert len(payload["entries"]) == 20
    assert payload["entries"][0]["rank"] == 101