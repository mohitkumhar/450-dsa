import app.leaderboard.routes as leaderboard_routes
import app.leaderboard.service as leaderboard_service
from conftest import build_test_app


def test_api_leaderboard_defaults_invalid_pagination_values(monkeypatch):
    flask_app, _ = build_test_app(
        monkeypatch,
        extra_db_targets=(leaderboard_service,),
    )

    monkeypatch.setattr(
        leaderboard_routes,
        "build_leaderboard_data",
        lambda: [
            {
                "user_id": "1",
                "name": "Alice",
                "profile_photo": "",
                "college": "A",
                "c_score": 10,
                "total_solved": 5,
                "dsa_done": 3,
                "lc_total": 1,
                "lc_rating": 1200,
            }
        ],
    )

    with flask_app.test_client() as client:
        response = client.get("/api/leaderboard?page=abc&per_page=")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 1
    assert payload["per_page"] == 20
    assert payload["total"] == 1
    assert payload["total_pages"] == 1
    assert payload["entries"][0]["rank"] == 1
