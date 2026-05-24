from bson import ObjectId

import app.tracker.routes as tracker_routes
from conftest import build_test_app, login_test_user


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
