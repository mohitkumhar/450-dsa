import app as app_module
import app.search.service as search_service
import app.tracker.routes as tracker_routes
import app.utils as utils
from conftest import build_test_app


class FakeCache:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, timeout=None):
        self.values[key] = value
        self.set_calls.append((key, timeout))


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs
        self.limit_count = None

    def sort(self, args):
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def __iter__(self):
        return iter(self.docs[: self.limit_count])


class FakeQuestionCollection:
    def __init__(self, docs):
        self.docs = docs
        self.find_calls = []

    def find(self, query, projection):
        self.find_calls.append((query, projection))
        return FakeCursor(self.docs)


class FakeTopicCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection):
        requested_ids = set(query.get("_id", {}).get("$in", []))
        return [doc for doc in self.docs if doc["_id"] in requested_ids]


class FakeDB:
    def __init__(self, questions=None, topics=None):
        self.question = FakeQuestionCollection(questions or [])
        self.topic = FakeTopicCollection(topics or [])


def build_fake_search_db():
    return FakeDB(
        questions=[
            {
                "_id": "q1",
                "problem": "Two Sum",
                "topic": "arrays",
                "url": "https://leetcode.com/problems/two-sum/",
                "url2": "",
                "score": 5.0,
            },
            {
                "_id": "q2",
                "problem": "Two Sum Variant",
                "topic": "arrays",
                "url": "https://practice.geeksforgeeks.org/problems/two-sum-variant/",
                "url2": "",
                "score": 4.0,
            },
        ],
        topics=[{"_id": "arrays", "name": "Arrays", "position": 1}],
    )


def test_search_reuses_cached_results_for_normalized_query(monkeypatch):
    fake_db = build_fake_search_db()
    fake_cache = FakeCache()

    monkeypatch.setattr(utils, "db", fake_db)
    monkeypatch.setattr(search_service, "cache", fake_cache)

    first = utils.search_dsa_questions("  Two   Sum  ", limit=10)
    second = utils.search_dsa_questions("two sum", limit=10)

    assert len(fake_db.question.find_calls) == 1
    assert first["results"] == second["results"]
    assert second["query"] == "two sum"


def test_search_cache_key_includes_limit_and_platform_filters(monkeypatch):
    fake_db = build_fake_search_db()
    fake_cache = FakeCache()

    monkeypatch.setattr(utils, "db", fake_db)
    monkeypatch.setattr(search_service, "cache", fake_cache)

    utils.search_dsa_questions("two sum", limit=10)
    utils.search_dsa_questions("two sum", limit=20)
    utils.search_dsa_questions("gfg two sum", limit=10)

    assert len(fake_db.question.find_calls) == 3


def test_invalidate_search_question_cache_bumps_cache_version(monkeypatch):
    fake_db = build_fake_search_db()
    fake_cache = FakeCache()

    monkeypatch.setattr(utils, "db", fake_db)
    monkeypatch.setattr(search_service, "cache", fake_cache)

    utils.search_dsa_questions("two sum", limit=10)
    search_service.invalidate_search_question_cache()
    utils.search_dsa_questions("two sum", limit=10)

    assert len(fake_db.question.find_calls) == 2
    assert fake_cache.values[search_service.SEARCH_QUERY_CACHE_VERSION_KEY] == 2


def test_initial_question_seed_invalidates_search_cache(monkeypatch):
    invalidations = []
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))

    monkeypatch.setattr(app_module, "invalidate_search_question_cache", lambda: invalidations.append("cleared"))
    flask_app._db_initialized = False

    with flask_app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert invalidations
    assert test_db.topic.count_documents({}) > 0
    assert test_db.question.count_documents({}) > 0
