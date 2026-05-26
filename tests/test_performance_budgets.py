import re

import app.leaderboard.service as leaderboard_service
import app.profile.routes as profile_routes
import app.tracker.routes as tracker_routes
from conftest import build_test_app, login_test_user


PAGE_BUDGETS = {
    "/": {"html_bytes": 47_000, "js_bytes": 8_000, "initial_requests": 6},
    "/search": {"html_bytes": 56_000, "js_bytes": 16_500, "initial_requests": 6},
    "/leaderboard": {"html_bytes": 55_000, "js_bytes": 16_000, "initial_requests": 6},
    "/profile": {"html_bytes": 90_000, "js_bytes": 23_000, "initial_requests": 7},
}


def _seed_profile_pages(test_db):
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    for index in range(5):
        test_db.question.insert_one(
            {
                "topic": topic_id,
                "problem": f"Question {index}",
                "difficulty": "Easy",
                "url": "https://example.com/problem",
                "url2": "",
            }
        )

    return test_db.user.insert_one(
        {
            "email": "user@example.com",
            "name": "User",
            "progress": {},
            "is_admin": False,
            "external_daily_counts": {},
            "external_totals": {},
            "rating_history": [],
            "lc_badges_json": "[]",
            "hr_badges_json": "[]",
            "bio": "",
            "headline": "",
            "location": "",
            "college": "",
            "linkedin_url": "",
            "twitter_url": "",
            "website_url": "",
            "resume_url": "",
            "leetcode_username": "",
            "github_username": "",
            "gfg_username": "",
            "codingninjas_username": "",
            "hackerrank_username": "",
            "atcoder_username": "",
        }
    ).inserted_id


def _page_metrics(response):
    html = response.get_data(as_text=True)
    return {
        "html_bytes": len(response.data),
        "js_bytes": sum(
            len(match.encode("utf-8"))
            for match in re.findall(r"<script(?:[^>]*)>(.*?)</script>", html, re.S)
        ),
        "initial_requests": (
            len(re.findall(r"<script[^>]+src=", html))
            + len(re.findall(r'<link[^>]+rel=["\']stylesheet["\']', html))
            + len(re.findall(r'loading=["\']eager["\']', html))
        ),
    }


def test_major_pages_stay_within_frontend_performance_budgets(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(
            profile_routes,
            leaderboard_service,
            tracker_routes,
        ),
    )
    user_id = _seed_profile_pages(test_db)
    client = flask_app.test_client()
    login_test_user(client, user_id)

    for path, budget in PAGE_BUDGETS.items():
        response = client.get(path)

        assert response.status_code == 200
        metrics = _page_metrics(response)

        assert metrics["html_bytes"] <= budget["html_bytes"], (path, "html_bytes", metrics)
        assert metrics["js_bytes"] <= budget["js_bytes"], (path, "js_bytes", metrics)
        assert metrics["initial_requests"] <= budget["initial_requests"], (
            path,
            "initial_requests",
            metrics,
        )
