from bson import ObjectId

import app.tracker.routes as tracker_routes
from conftest import build_test_app, login_test_user


def test_notes_search_returns_only_matching_private_notes(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    arrays_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    graphs_id = test_db.topic.insert_one({"name": "Graphs", "position": 2}).inserted_id
    arrays_question_id = test_db.question.insert_one({"topic": arrays_id, "problem": "Two Sum"}).inserted_id
    graphs_question_id = test_db.question.insert_one({"topic": graphs_id, "problem": "Clone Graph"}).inserted_id

    with flask_app.test_client() as client:
        user_id = test_db.user.insert_one(
            {
                "email": "user@example.com",
                "progress": {
                    str(arrays_question_id): {"notes": "Remember hash map for complement lookup"},
                    str(graphs_question_id): {"notes": "Use BFS copy approach"},
                },
                "is_admin": False,
            }
        ).inserted_id
        login_test_user(client, user_id)
        response = client.get("/notes/search?q=hash")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Two Sum" in html
    assert "Remember hash map for complement lookup" in html
    assert "Clone Graph" not in html
    assert "Use BFS copy approach" not in html


def test_notes_search_uses_minimal_question_projection(monkeypatch):
    class RecordingQuestionCollection:
        def __init__(self, documents):
            self.documents = list(documents)
            self.find_calls = []

        def find(self, query=None, projection=None):
            query = query or {}
            self.find_calls.append((query, projection))
            ids = set(query.get("_id", {}).get("$in", []))
            return [document for document in self.documents if document["_id"] in ids]

    topic_id = ObjectId()
    question_id = ObjectId()
    question_collection = RecordingQuestionCollection(
        [{"_id": question_id, "topic": topic_id, "problem": "Two Sum"}]
    )
    fake_db = type(
        "FakeDB",
        (),
        {
            "question": question_collection,
            "topic": type(
                "FakeTopicCollection",
                (),
                {
                    "find": lambda self, query, projection=None: [{"_id": topic_id, "name": "Arrays"}],
                },
            )(),
        },
    )()

    monkeypatch.setattr(tracker_routes, "db", fake_db)
    monkeypatch.setattr(
        tracker_routes,
        "current_user",
        type(
            "FakeUser",
            (),
            {
                "is_authenticated": True,
                "progress": {str(question_id): {"notes": "Hash map reminder"}},
            },
        )(),
    )
    captured = {}
    monkeypatch.setattr(
        tracker_routes,
        "render_template",
        lambda template, **context: captured.update({"template": template, "context": context}) or context,
    )

    flask_app = flask_app = build_test_app(monkeypatch, extra_db_targets=())[0]
    with flask_app.test_request_context("/notes/search?q=hash"):
        tracker_routes.search_notes.__wrapped__()

    assert question_collection.find_calls == [
        (
            {"_id": {"$in": [question_id]}},
            tracker_routes.NOTES_SEARCH_QUESTION_PROJECTION,
        )
    ]
    assert captured["template"] == "notes_search.html"
