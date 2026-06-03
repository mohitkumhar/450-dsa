from bson import ObjectId

import app.tracker.routes as tracker_routes
from conftest import build_test_app, csrf_headers, login_test_user


def test_topic_not_found_invalid_id(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))

    with flask_app.test_client() as client:
        response = client.get("/topic/invalid-object-id")

    assert response.status_code == 404
    assert b"Topic not found" in response.data


def test_topic_not_found_missing_id(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    non_existent_id = str(ObjectId())

    with flask_app.test_client() as client:
        response = client.get(f"/topic/{non_existent_id}")

    assert response.status_code == 404
    assert b"Topic not found" in response.data


def test_topic_page_all_and_filtered_counts(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))

    # Insert a test topic
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id

    # Insert test questions with various difficulties
    test_db.question.insert_many([
        {"topic": topic_id, "problem": "Easy Prob 1", "difficulty": "Easy"},
        {"topic": topic_id, "problem": "Easy Prob 2", "difficulty": "Easy"},
        {"topic": topic_id, "problem": "Medium Prob 1", "difficulty": "Medium"},
        {"topic": topic_id, "problem": "Hard Prob 1", "difficulty": "Hard"},
        {"topic": topic_id, "problem": "Default Medium Prob"}, # No difficulty field, should default to Medium
    ])

    # 1. Test topic page with NO filter (all)
    with flask_app.test_client() as client:
        response = client.get(f"/topic/{topic_id}")

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Verify All, Easy, Medium, Hard counts on the filter buttons
    assert "All (5)" in html
    assert "Easy (2)" in html
    assert "Medium (2)" in html
    assert "Hard (1)" in html

    # Verify subtitle
    assert "5 questions in this topic" in html

    # Verify all problems are rendered
    assert "Easy Prob 1" in html
    assert "Easy Prob 2" in html
    assert "Medium Prob 1" in html
    assert "Hard Prob 1" in html
    assert "Default Medium Prob" in html

    # 2. Test topic page filtered by Easy difficulty
    with flask_app.test_client() as client:
        response = client.get(f"/topic/{topic_id}?difficulty=Easy")

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Verify counts on buttons still reflect full counts
    assert "All (5)" in html
    assert "Easy (2)" in html
    assert "Medium (2)" in html
    assert "Hard (1)" in html

    # Verify subtitle shows filtered info
    assert "Showing 2 of 5 questions (Easy difficulty)" in html

    # Verify only Easy questions are present in table/body
    assert "Easy Prob 1" in html
    assert "Easy Prob 2" in html
    assert "Medium Prob 1" not in html
    assert "Hard Prob 1" not in html


def test_topic_page_status_filters_include_skipped_counts(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_ids = test_db.question.insert_many([
        {"topic": topic_id, "problem": "Two Sum", "difficulty": "Easy"},
        {"topic": topic_id, "problem": "Merge Intervals", "difficulty": "Medium"},
        {"topic": topic_id, "problem": "Jump Game", "difficulty": "Hard"},
    ]).inserted_ids
    progress = {
        str(question_ids[0]): {"done": True},
        str(question_ids[1]): {"skipped": True},
    }
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": progress, "is_admin": False}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get(f"/topic/{topic_id}?status=skipped")

    html = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Done (1)" in html
    assert "Skipped (1)" in html
    assert "To Do (1)" in html
    assert "Showing 1 of 3 questions (Skipped status)" in html
    assert "Merge Intervals" in html
    assert "Two Sum" not in html
    assert "Jump Game" not in html
    assert "Default Medium Prob" not in html


def test_update_question_rejects_missing_json_body(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", headers=csrf_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object",
    }


def test_update_question_rejects_malformed_json(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(
            f"/update_question/{question_id}",
            data="{not-json",
            content_type="application/json",
            headers=csrf_headers(client),
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Request body must be a JSON object"


def test_update_question_rejects_json_array(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json=["done"], headers=csrf_headers(client))

    assert response.status_code == 400
    assert response.get_json()["error"] == "Request body must be a JSON object"


def test_update_question_rejects_non_boolean_done(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(
            f"/update_question/{question_id}",
            json={"done": "true"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "done must be a boolean"}


def test_update_question_rejects_non_boolean_skipped(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(
            f"/update_question/{question_id}",
            json={"skipped": "true"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "skipped must be a boolean"}


def test_topic_page_accepts_lowercase_difficulty_filter(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    test_db.question.insert_many([
        {"topic": topic_id, "problem": "Easy Prob", "difficulty": "Easy"},
        {"topic": topic_id, "problem": "Hard Prob", "difficulty": "Hard"},
    ])

    with flask_app.test_client() as client:
        response = client.get(f"/topic/{topic_id}?difficulty=easy")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Showing 1 of 2 questions (Easy difficulty)" in html
    assert "Easy Prob" in html
    assert "Hard Prob" not in html


def test_topic_page_ignores_unknown_difficulty_filter(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    test_db.question.insert_many([
        {"topic": topic_id, "problem": "Easy Prob", "difficulty": "Easy"},
        {"topic": topic_id, "problem": "Hard Prob", "difficulty": "Hard"},
    ])

    with flask_app.test_client() as client:
        response = client.get(f"/topic/{topic_id}?difficulty=Invalid")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "2 questions in this topic" in html
    assert "Showing 0 of 2 questions" not in html
    assert "Easy Prob" in html
    assert "Hard Prob" in html


def test_update_question_accepts_valid_boolean_update(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one(
        {"problem": "Two Sum", "url": "https://leetcode.com/problems/two-sum/"}
    ).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json={"done": True}, headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"][str(question_id)]
    assert progress["done"] is True
    assert "timestamp" in progress
    assert user["in_sheet_platform_counts"]["LeetCode"] == 1


def test_topic_page_exposes_reset_progress_button(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    test_db.question.insert_one({"topic": topic_id, "problem": "Two Sum", "url": "https://leetcode.com/problems/two-sum/"})
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": {}, "is_admin": False}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get(f"/topic/{topic_id}")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Reset Progress" in html


def test_reset_topic_progress_clears_topic_question_status(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    topic_question_id = test_db.question.insert_one(
        {"topic": topic_id, "problem": "Two Sum", "url": "https://leetcode.com/problems/two-sum/"}
    ).inserted_id
    other_topic_id = test_db.topic.insert_one({"name": "Graphs", "position": 2}).inserted_id
    other_question_id = test_db.question.insert_one(
        {"topic": other_topic_id, "problem": "Flood Fill", "url": "https://www.geeksforgeeks.org/flood-fill-algorithm/"}
    ).inserted_id
    user_id = test_db.user.insert_one(
        {
            "email": "user@example.com",
            "progress": {
                str(topic_question_id): {"done": True, "skipped": True},
                str(other_question_id): {"done": True},
            },
            "is_admin": False,
            "in_sheet_platform_counts": {
                "LeetCode": 1,
                "GFG": 1,
                "Coding Ninjas": 0,
                "HackerRank": 0,
                "AtCoder": 0,
                "Codewars": 0,
            },
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post(f"/topic/{topic_id}/reset-progress", headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True

    user = test_db.user.find_one({"_id": user_id})
    topic_progress = user["progress"][str(topic_question_id)]
    assert topic_progress.get("done") is None
    assert topic_progress.get("skipped") is None
    assert user["progress"][str(other_question_id)]["done"] is True
    assert user["in_sheet_platform_counts"]["LeetCode"] == 0
    assert user["in_sheet_platform_counts"]["GFG"] == 1


def test_update_question_sets_skipped_and_clears_done(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one(
        {"problem": "Two Sum", "url": "https://leetcode.com/problems/two-sum/"}
    ).inserted_id
    user_id = test_db.user.insert_one(
        {
            "email": "user@example.com",
            "progress": {str(question_id): {"done": True, "skipped": False}},
            "in_sheet_platform_counts": {"LeetCode": 1},
            "is_admin": False,
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post(f"/update_question/{question_id}", json={"skipped": True}, headers=csrf_headers(client))

    assert response.status_code == 200
    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"][str(question_id)]
    assert progress["skipped"] is True
    assert progress["done"] is False
    assert user["in_sheet_platform_counts"]["LeetCode"] == 0


# Offline queue sync tests

def test_offline_queue_done_syncs_on_reconnect(monkeypatch):
    """Queued 'done' change flushes successfully once back online."""
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Binary Search"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json={"done": True}, headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    assert user["progress"][str(question_id)]["done"] is True


def test_offline_queue_bookmark_syncs_on_reconnect(monkeypatch):
    """Queued 'bookmark' change flushes successfully once back online."""
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Merge Sort"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(
            f"/update_question/{question_id}", json={"bookmark": True}, headers=csrf_headers(client)
        )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    assert user["progress"][str(question_id)]["bookmark"] is True


def test_offline_queue_notes_syncs_on_reconnect(monkeypatch):
    """Queued 'notes' change flushes successfully once back online."""
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Linked List"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(
            f"/update_question/{question_id}",
            json={"notes": "use slow/fast pointer"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    assert user["progress"][str(question_id)]["notes"] == "use slow/fast pointer"


def test_offline_queue_merged_payload_syncs_on_reconnect(monkeypatch):
    """Merged offline queue entry (done + bookmark + notes) flushes in one request."""
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Graph BFS"}).inserted_id

    merged_payload = {"done": True, "bookmark": True, "notes": "BFS uses a queue"}

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json=merged_payload, headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"][str(question_id)]
    assert progress["done"] is True
    assert progress["bookmark"] is True
    assert progress["notes"] == "BFS uses a queue"


def test_offline_queue_last_write_wins_conflict(monkeypatch):
    """Second flush overwrites first; last-write-wins conflict resolution."""
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "DP Knapsack"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        client.post(f"/update_question/{question_id}", json={"done": True}, headers=csrf_headers(client))
        response = client.post(f"/update_question/{question_id}", json={"done": False}, headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    assert user["progress"][str(question_id)]["done"] is False
