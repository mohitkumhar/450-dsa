import app.tracker.routes as tracker_routes
from conftest import build_test_app

def test_questions_with_and_without_hints(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))

    # Insert a test topic
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id

    # Insert a question without hints
    q_no_hints_id = test_db.question.insert_one({
        "topic": topic_id,
        "problem": "No Hints Problem",
        "difficulty": "Easy",
        "url": "https://leetcode.com/problems/no-hints",
    }).inserted_id

    # Insert a question with multiple hints
    q_with_hints_id = test_db.question.insert_one({
        "topic": topic_id,
        "problem": "With Hints Problem",
        "difficulty": "Medium",
        "url": "https://leetcode.com/problems/with-hints",
        "hints": ["Hint A", "Hint B"]
    }).inserted_id

    with flask_app.test_client() as client:
        response = client.get(f"/topic/{topic_id}")

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Verify both questions are present in HTML
    assert "No Hints Problem" in html
    assert "With Hints Problem" in html

    # Verify that the question without hints doesn't render hint UI elements
    assert f"hints-container-{q_no_hints_id}" not in html

    # Verify that the question with hints does render the hints UI elements
    assert f"hints-container-{q_with_hints_id}" in html
    assert 'data-hints-total="2"' in html
    assert 'data-hints-revealed="0"' in html
    assert "Hint A" in html
    assert "Hint B" in html
