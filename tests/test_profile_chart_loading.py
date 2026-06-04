import re
from pathlib import Path

import app.leaderboard.service as leaderboard_service
import app.profile.routes as profile_routes
from conftest import build_test_app, login_test_user


PROFILE_TEMPLATE = Path("templates/profile.html").read_text(encoding="utf-8")
DIFFICULTY_CHART_PATTERN = re.compile(
    r"\[\s*'difficultyChart'\s*,\s*'difficultyChartShell'\s*,"
    r"\s*\[\s*'Easy'\s*,\s*'Medium'\s*,\s*'Hard'\s*\]\s*,"
    r"\s*\[(?P<values>[^\]]+)\]"
)


def extract_difficulty_chart_values(html):
    match = DIFFICULTY_CHART_PATTERN.search(html)
    assert match is not None
    return [float(value.strip()) for value in match.group("values").split(",")]


def test_profile_does_not_eager_load_chartjs_in_head():
    head = PROFILE_TEMPLATE.split("{% block content %}", 1)[0]

    assert "cdn.jsdelivr.net/npm/chart.js" not in head
    assert "unpkg.com/chart.js" not in head


def test_profile_lazy_loads_charts_on_intersection():
    assert "function loadChartJs()" in PROFILE_TEMPLATE
    assert "new IntersectionObserver" in PROFILE_TEMPLATE
    assert "renderProfileCharts()" in PROFILE_TEMPLATE


def test_profile_difficulty_chart_uses_synced_leetcode_totals(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, leaderboard_service),
    )

    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    easy_id = test_db.question.insert_one(
        {
            "topic": topic_id,
            "problem": "Reverse Array",
            "difficulty": "Easy",
        }
    ).inserted_id
    medium_id = test_db.question.insert_one(
        {
            "topic": topic_id,
            "problem": "Merge Intervals",
            "difficulty": "Medium",
        }
    ).inserted_id

    user_id = test_db.user.insert_one(
        {
            "name": "Synced User",
            "email": "synced@example.com",
            "progress": {
                str(easy_id): {"done": True},
                str(medium_id): {"done": True},
            },
            "external_totals": {
                "LeetCode": 42,
                "LeetCode_Easy": 11,
                "LeetCode_Medium": 22,
                "LeetCode_Hard": 9,
            },
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/profile")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert extract_difficulty_chart_values(html) == [11, 22, 9]


def test_profile_difficulty_chart_defaults_unsynced_leetcode_totals_to_zero(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, leaderboard_service),
    )

    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    easy_id = test_db.question.insert_one(
        {
            "topic": topic_id,
            "problem": "Reverse Array",
            "difficulty": "Easy",
        }
    ).inserted_id

    user_id = test_db.user.insert_one(
        {
            "name": "Unsynced User",
            "email": "unsynced@example.com",
            "progress": {str(easy_id): {"done": True}},
            "external_totals": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/profile")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert extract_difficulty_chart_values(html) == [0, 0, 0]


def test_profile_difficulty_chart_defaults_missing_external_totals_to_zero(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, leaderboard_service),
    )

    user_id = test_db.user.insert_one(
        {
            "name": "Missing Totals User",
            "email": "missing@example.com",
            "progress": {},
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/profile")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert extract_difficulty_chart_values(html) == [0, 0, 0]


def test_profile_difficulty_chart_coerces_none_and_missing_leetcode_totals_to_zero(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, leaderboard_service),
    )

    user_id = test_db.user.insert_one(
        {
            "name": "Partial Totals User",
            "email": "partial@example.com",
            "progress": {},
            "external_totals": {
                "LeetCode_Easy": None,
                "LeetCode_Medium": 2,
            },
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/profile")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert extract_difficulty_chart_values(html) == [0, 2, 0]
