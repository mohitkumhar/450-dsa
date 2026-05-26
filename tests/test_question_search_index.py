import app as app_module
import app.search.service as search_service
import app.tracker.routes as tracker_routes
from conftest import build_test_app


def test_build_question_search_text_includes_topic_and_platform_terms():
    search_text = search_service.build_question_search_text(
        {
            "problem": "Two Sum",
            "url": "https://leetcode.com/problems/two-sum/",
            "url2": "https://practice.geeksforgeeks.org/problems/two-sum/",
        },
        "Arrays",
    )

    assert "Two Sum" in search_text
    assert "Arrays" in search_text
    assert "LeetCode" in search_text
    assert "leetcode" in search_text
    assert "GFG" in search_text
    assert "geeksforgeeks" in search_text


def test_create_app_expands_problem_text_index_with_search_text(monkeypatch):
    _, test_db = build_test_app(monkeypatch)

    index_keys = test_db.question.index_information()["problem_text"]["key"]

    assert index_keys == [("problem", "text"), ("search_text", "text")]


def test_existing_questions_get_search_text_backfill_on_first_request(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_id = test_db.question.insert_one(
        {
            "topic": topic_id,
            "problem": "Two Sum",
            "url": "https://leetcode.com/problems/two-sum/",
            "url2": "",
        }
    ).inserted_id
    flask_app._db_initialized = False

    with flask_app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    question = test_db.question.find_one({"_id": question_id})
    assert question["search_text"] == "Two Sum Arrays LeetCode lc leetcode leet code"


def test_question_search_index_is_recreated_when_legacy_spec_is_present(monkeypatch):
    class FakeQuestionCollection:
        def __init__(self):
            self.create_calls = []
            self.drop_calls = []

        def index_information(self):
            return {"problem_text": {"key": [("problem", "text")]}}

        def drop_index(self, name):
            self.drop_calls.append(name)

        def create_index(self, keys, name=None):
            self.create_calls.append((keys, name))

    fake_question = FakeQuestionCollection()
    fake_db = type("FakeDB", (), {"question": fake_question})()

    monkeypatch.setattr(app_module, "db", fake_db)

    app_module._ensure_question_search_index()

    assert fake_question.drop_calls == ["problem_text"]
    assert fake_question.create_calls == [
        ([("problem", "text"), ("search_text", "text")], "problem_text")
    ]
