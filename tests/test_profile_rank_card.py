from pathlib import Path

from bson import ObjectId

import app.leaderboard.service as leaderboard_service
import app.profile.routes as profile_routes
from conftest import build_test_app, login_test_user


def test_profile_template_uses_rank_variable_not_formula():
    template_path = Path(__file__).resolve().parents[1] / "templates" / "profile.html"
    html = template_path.read_text(encoding="utf-8")

    assert "{{ dsa_done * 2 + (lc_easy + lc_medium * 2 + lc_hard * 3) }}" not in html
    assert "profile_leaderboard_rank" in html


def test_profile_page_displays_real_local_leaderboard_rank(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, leaderboard_service),
    )

    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_id = test_db.question.insert_one(
        {
            "_id": ObjectId(),
            "topic": topic_id,
            "problem": "Two Sum",
            "url": "https://leetcode.com/problems/two-sum",
            "difficulty": "Easy",
        }
    ).inserted_id

    higher_user_id = test_db.user.insert_one(
        {
            "name": "Higher Rank",
            "email": "higher@example.com",
            "progress": {str(question_id): {"done": True}},
            "external_totals": {"LeetCode": 20, "LeetCode_Easy": 8, "LeetCode_Medium": 8, "LeetCode_Hard": 4},
        }
    ).inserted_id
    current_user_id = test_db.user.insert_one(
        {
            "name": "Current User",
            "email": "current@example.com",
            "progress": {str(question_id): {"done": True}},
            "external_totals": {"LeetCode": 10, "LeetCode_Easy": 5, "LeetCode_Medium": 3, "LeetCode_Hard": 2},
        }
    ).inserted_id

    score_map = {
        str(higher_user_id): {
            "c_score": 200,
            "dsa_done": 1,
            "lc_total": 20,
            "lc_easy": 8,
            "lc_medium": 8,
            "lc_hard": 4,
            "lc_rating": 1700,
            "gfg_total": 0,
            "hr_total": 0,
            "cn_total": 0,
            "active_days": 1,
            "total_solved": 21,
        },
        str(current_user_id): {
            "c_score": 150,
            "dsa_done": 1,
            "lc_total": 10,
            "lc_easy": 5,
            "lc_medium": 3,
            "lc_hard": 2,
            "lc_rating": 1500,
            "gfg_total": 0,
            "hr_total": 0,
            "cn_total": 0,
            "active_days": 1,
            "total_solved": 11,
        },
    }

    monkeypatch.setattr(
        leaderboard_service,
        "compute_c_score",
        lambda user, all_questions=None: score_map[str(user["_id"])],
    )

    with flask_app.test_client() as client:
        login_test_user(client, current_user_id)
        response = client.get("/profile")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Current User" in html
    assert '<span class="rank-num">2</span>' in html
