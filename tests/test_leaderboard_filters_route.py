import app.leaderboard.service as leaderboard_service
from tests.conftest import build_test_app


def test_api_leaderboard_filtering_by_college(monkeypatch):
    app, test_db = build_test_app(monkeypatch, extra_db_targets=(leaderboard_service,))

    test_db.user.insert_many([
        {
            "name": "Alice",
            "email": "alice@example.com",
            "college": "IIT Delhi",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {},
            "external_daily_counts": {},
        },
        {
            "name": "Bob",
            "email": "bob@example.com",
            "college": "BITS Pilani",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {},
            "external_daily_counts": {},
        }
    ])

    with app.test_client() as client:
        # Fetch with IIT Delhi filter
        response = client.get("/api/leaderboard?college=iit%20delhi")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["name"] == "Alice"

        # Fetch with BITS Pilani filter
        response = client.get("/api/leaderboard?college=BITS%20Pilani")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["name"] == "Bob"

        # Fetch with unknown college
        response = client.get("/api/leaderboard?college=Unknown")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["entries"]) == 0


def test_api_leaderboard_filtering_by_platform(monkeypatch):
    app, test_db = build_test_app(monkeypatch, extra_db_targets=(leaderboard_service,))

    test_db.user.insert_many([
        {
            "name": "Alice",
            "email": "alice@example.com",
            "college": "IIT Delhi",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {"LeetCode": 10},
            "external_daily_counts": {},
        },
        {
            "name": "Bob",
            "email": "bob@example.com",
            "college": "BITS Pilani",
            "progress": {},
            "is_admin": False,
            "is_deactivated": False,
            "external_totals": {"GFG": 5},
            "external_daily_counts": {},
        }
    ])

    with app.test_client() as client:
        # Fetch with LeetCode platform filter
        response = client.get("/api/leaderboard?platform=leetcode")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["name"] == "Alice"

        # Fetch with GFG platform filter
        response = client.get("/api/leaderboard?platform=GFG")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["name"] == "Bob"
