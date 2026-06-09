from bson import ObjectId

import app.leaderboard.service as leaderboard_service
import app.profile.routes as profile_routes
from conftest import build_test_app, login_test_user


def test_profile_platform_counts_set_is_conditional(monkeypatch):
    """When in_sheet_platform_counts is missing, /profile should write it using
    a conditional $set so it can't clobber a concurrent $inc from /update_question."""
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

    # Note: intentionally omit in_sheet_platform_counts so /profile computes + caches it.
    user_id = test_db.user.insert_one(
        {
            "name": "User",
            "email": "user@example.com",
            "progress": {str(question_id): {"done": True}},
            "external_totals": {},
        }
    ).inserted_id

    original_update_one = test_db.user.update_one
    seen_filters = []

    def wrapped_update_one(filter_doc, update_doc, *args, **kwargs):
        seen_filters.append(filter_doc)
        return original_update_one(filter_doc, update_doc, *args, **kwargs)

    monkeypatch.setattr(test_db.user, "update_one", wrapped_update_one)

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/profile")

    assert response.status_code == 200
    assert seen_filters, "Expected /profile to attempt caching in_sheet_platform_counts"
    assert any(
        f.get("in_sheet_platform_counts") == {"$exists": False} for f in seen_filters
    ), "Expected conditional $exists filter to avoid clobbering concurrent $inc updates"
