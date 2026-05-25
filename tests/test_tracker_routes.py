from bson import ObjectId

import app.tracker.routes as tracker_routes
from conftest import build_test_app, login_test_user


def set_csrf_token(client, token="test-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


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
    assert "Default Medium Prob" not in html


    # 3. Test topic page filtered by Medium difficulty
    with flask_app.test_client() as client:
        response = client.get(f"/topic/{topic_id}?difficulty=Medium")

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Verify counts on buttons still reflect full counts
    assert "All (5)" in html
    assert "Easy (2)" in html
    assert "Medium (2)" in html
    assert "Hard (1)" in html

    # Verify subtitle shows filtered info
    assert "Showing 2 of 5 questions (Medium difficulty)" in html

    # Verify only Medium questions are present in table/body
    assert "Medium Prob 1" in html
    assert "Default Medium Prob" in html
    assert "Easy Prob 1" not in html
    assert "Easy Prob 2" not in html
    assert "Hard Prob 1" not in html


def test_update_question_rejects_missing_json_body(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}")

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
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Request body must be a JSON object"


def test_update_question_rejects_json_array(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json=["done"])

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
        )

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "done must be a boolean"}


def test_update_question_accepts_valid_boolean_update(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    question_id = test_db.question.insert_one({"problem": "Two Sum"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(f"/update_question/{question_id}", json={"done": True})

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"][str(question_id)]
    assert progress["done"] is True
    assert "timestamp" in progress


def test_topic_page_shows_reset_summary_for_authenticated_user(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_ids = test_db.question.insert_many(
        [
            {"topic": topic_id, "problem": "Two Sum"},
            {"topic": topic_id, "problem": "Three Sum"},
        ]
    ).inserted_ids

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        test_db.user.update_one(
            {"_id": user_id},
            {
                "$set": {
                    f"progress.{question_ids[0]}.done": True,
                    f"progress.{question_ids[1]}.bookmark": True,
                }
            },
        )
        response = client.get(f"/topic/{topic_id}")

    html = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Reset Topic" in html
    assert "This will clear saved progress for 2 tracked question(s) in Arrays." in html


def test_reset_topic_progress_clears_only_topic_entries(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    other_topic_id = test_db.topic.insert_one({"name": "Graphs", "position": 2}).inserted_id
    topic_question_ids = test_db.question.insert_many(
        [
            {"topic": topic_id, "problem": "Two Sum"},
            {"topic": topic_id, "problem": "Three Sum"},
        ]
    ).inserted_ids
    other_question_id = test_db.question.insert_one({"topic": other_topic_id, "problem": "DFS"}).inserted_id

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        set_csrf_token(client)
        test_db.user.update_one(
            {"_id": user_id},
            {
                "$set": {
                    f"progress.{topic_question_ids[0]}.done": True,
                    f"progress.{topic_question_ids[1]}.bookmark": True,
                    f"progress.{other_question_id}.done": True,
                }
            },
        )
        response = client.post(
            f"/topic/{topic_id}/reset-progress",
            data={"csrf_token": "test-csrf-token"},
        )

    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"]
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert str(topic_question_ids[0]) not in progress
    assert str(topic_question_ids[1]) not in progress
    assert progress[str(other_question_id)]["done"] is True


def test_reset_topic_progress_rejects_missing_csrf(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        set_csrf_token(client)
        response = client.post(f"/topic/{topic_id}/reset-progress", data={})

    assert response.status_code == 400


def test_reset_topic_progress_returns_success_when_nothing_to_clear(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    test_db.question.insert_one({"topic": topic_id, "problem": "Two Sum"})

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        set_csrf_token(client)
        response = client.post(
            f"/topic/{topic_id}/reset-progress",
            data={"csrf_token": "test-csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json()["message"] == "No saved progress found for Arrays."
