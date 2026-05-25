from types import SimpleNamespace

from bson import ObjectId
from flask import Flask

import app.tracker.routes as tracker_routes


class FakeCursor(list):
    def sort(self, key, direction):
        reverse = direction == -1
        return FakeCursor(sorted(self, key=lambda item: item.get(key, 0), reverse=reverse))


def _apply_projection(document, projection):
    if projection is None:
        return dict(document)

    included_keys = {key for key, enabled in projection.items() if enabled and not isinstance(enabled, dict)}
    projected = {key: value for key, value in document.items() if key in included_keys or key == "_id"}
    return projected


class RecordingQuestionCollection:
    def __init__(self, documents):
        self.documents = list(documents)
        self.find_calls = []
        self.find_one_calls = []

    def count_documents(self, query):
        return len(self._filter(query))

    def find(self, query=None, projection=None):
        query = query or {}
        self.find_calls.append((query, projection))
        return FakeCursor([_apply_projection(document, projection) for document in self._filter(query)])

    def find_one(self, query, projection=None):
        self.find_one_calls.append((query, projection))
        matches = self._filter(query)
        if not matches:
            return None
        return _apply_projection(matches[0], projection)

    def _filter(self, query):
        if not query:
            return list(self.documents)

        results = []
        for document in self.documents:
            matched = True
            for key, value in query.items():
                if isinstance(value, dict) and "$in" in value:
                    if document.get(key) not in value["$in"]:
                        matched = False
                        break
                elif document.get(key) != value:
                    matched = False
                    break
            if matched:
                results.append(document)
        return results


class FakeTopicCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    def find(self, query=None, projection=None):
        query = query or {}
        if not query:
            return FakeCursor([_apply_projection(document, projection) for document in self.documents])

        if "_id" in query and isinstance(query["_id"], dict) and "$in" in query["_id"]:
            ids = set(query["_id"]["$in"])
            return FakeCursor(
                [_apply_projection(document, projection) for document in self.documents if document["_id"] in ids]
            )

        return FakeCursor([])

    def find_one(self, query):
        for document in self.documents:
            if document["_id"] == query.get("_id"):
                return dict(document)
        return None


def test_index_uses_question_topic_projection(monkeypatch):
    question_collection = RecordingQuestionCollection(
        [
            {"_id": ObjectId(), "topic": "arrays", "problem": "Two Sum", "difficulty": "Easy"},
            {"_id": ObjectId(), "topic": "graphs", "problem": "DFS", "difficulty": "Medium"},
        ]
    )
    fake_db = SimpleNamespace(
        topic=FakeTopicCollection(
            [
                {"_id": "arrays", "name": "Arrays", "position": 1},
                {"_id": "graphs", "name": "Graphs", "position": 2},
            ]
        ),
        question=question_collection,
    )

    captured = {}
    monkeypatch.setattr(tracker_routes, "db", fake_db)
    monkeypatch.setattr(
        tracker_routes,
        "current_user",
        SimpleNamespace(is_authenticated=False, progress={}),
    )
    monkeypatch.setattr(
        tracker_routes,
        "render_template",
        lambda template, **context: captured.update({"template": template, "context": context}) or context,
    )

    flask_app = Flask(__name__)
    with flask_app.test_request_context("/"):
        tracker_routes.index()

    assert question_collection.find_calls == [({}, tracker_routes.INDEX_QUESTION_PROJECTION)]
    assert captured["template"] == "index.html"


def test_topic_and_notes_export_use_minimal_question_projections(monkeypatch):
    topic_id = ObjectId()
    question_collection = RecordingQuestionCollection(
        [
            {
                "_id": ObjectId(),
                "topic": topic_id,
                "problem": "Two Sum",
                "difficulty": "Easy",
                "url": "https://leetcode.com/problems/two-sum",
                "url2": "",
                "notes": "not from question docs",
            }
        ]
    )
    fake_db = SimpleNamespace(
        topic=FakeTopicCollection([{"_id": topic_id, "name": "Arrays", "position": 1}]),
        question=question_collection,
    )

    monkeypatch.setattr(tracker_routes, "db", fake_db)
    monkeypatch.setattr(
        tracker_routes,
        "current_user",
        SimpleNamespace(is_authenticated=True, progress={}),
    )
    monkeypatch.setattr(tracker_routes, "render_template", lambda template, **context: context)

    flask_app = Flask(__name__)
    with flask_app.test_request_context(f"/topic/{topic_id}"):
        tracker_routes.topic(str(topic_id))

    with flask_app.test_request_context(f"/topic/{topic_id}/export-notes"):
        response = tracker_routes.export_topic_notes.__wrapped__(str(topic_id))

    assert question_collection.find_calls[0] == (
        {"topic": topic_id},
        tracker_routes.TOPIC_PAGE_QUESTION_PROJECTION,
    )
    assert question_collection.find_calls[1] == (
        {"topic": topic_id},
        tracker_routes.TOPIC_NOTES_EXPORT_PROJECTION,
    )
    assert response.mimetype == "text/markdown"


def test_bookmarks_and_csv_export_use_question_projections(monkeypatch):
    topic_id = ObjectId()
    question_id = ObjectId()
    question_collection = RecordingQuestionCollection(
        [
            {
                "_id": question_id,
                "topic": topic_id,
                "problem": "Two Sum",
                "difficulty": "Easy",
                "url": "https://leetcode.com/problems/two-sum",
                "url2": "",
            }
        ]
    )
    fake_db = SimpleNamespace(
        topic=FakeTopicCollection([{"_id": topic_id, "name": "Arrays", "position": 1}]),
        question=question_collection,
    )

    monkeypatch.setattr(tracker_routes, "db", fake_db)
    monkeypatch.setattr(
        tracker_routes,
        "current_user",
        SimpleNamespace(
            is_authenticated=True,
            progress={str(question_id): {"bookmark": True, "done": True, "notes": "Review later"}},
        ),
    )
    monkeypatch.setattr(tracker_routes, "render_template", lambda template, **context: context)

    flask_app = Flask(__name__)
    with flask_app.test_request_context("/bookmarks"):
        tracker_routes.bookmarks.__wrapped__()

    with flask_app.test_request_context("/export/csv"):
        response = tracker_routes.export_csv.__wrapped__()

    assert question_collection.find_calls[0] == (
        {"_id": {"$in": [question_id]}},
        tracker_routes.BOOKMARKS_QUESTION_PROJECTION,
    )
    assert question_collection.find_calls[1] == (
        {},
        tracker_routes.CSV_EXPORT_QUESTION_PROJECTION,
    )
    assert response.mimetype == "text/csv"


def test_update_question_uses_problem_only_projection(monkeypatch):
    question_id = ObjectId()
    question_collection = RecordingQuestionCollection(
        [{"_id": question_id, "problem": "Two Sum", "difficulty": "Easy", "url": "https://leetcode.com"}]
    )
    fake_db = SimpleNamespace(
        topic=FakeTopicCollection([]),
        question=question_collection,
        user=SimpleNamespace(update_one=lambda *args, **kwargs: None),
    )

    current_user = SimpleNamespace(
        is_authenticated=True,
        id=ObjectId(),
        progress={},
        reload=lambda: None,
    )

    monkeypatch.setattr(tracker_routes, "db", fake_db)
    monkeypatch.setattr(tracker_routes, "current_user", current_user)

    flask_app = Flask(__name__)
    with flask_app.test_request_context(
        f"/update_question/{question_id}",
        method="POST",
        json={"done": True},
    ):
        response = tracker_routes.update_question.__wrapped__(str(question_id))

    assert question_collection.find_one_calls == [
        ({"_id": question_id}, tracker_routes.QUESTION_STATUS_PROJECTION)
    ]
    assert response.json["success"] is True
