from time import perf_counter

from bson.objectid import ObjectId

from app.leaderboard.service import build_leaderboard_data
from app.search.service import search_dsa_questions
from app.utils import compute_c_score


class FakeCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    def find(self, *args, **kwargs):
        return list(self.documents)


class FakeLeaderboardDB:
    def __init__(self, users, questions):
        self.user = FakeCollection(users)
        self.question = FakeCollection(questions)


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)
        self.limit_count = None

    def sort(self, args):
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def __iter__(self):
        docs = self.docs if self.limit_count is None else self.docs[: self.limit_count]
        return iter(docs)


class FakeQuestionCollection:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, query, projection):
        return FakeCursor(self.docs)


class FakeTopicCollection:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, query, projection):
        requested_ids = set(query.get("_id", {}).get("$in", []))
        return [doc for doc in self.docs if doc["_id"] in requested_ids]


class FakeSearchDB:
    def __init__(self, questions, topics):
        self.question = FakeQuestionCollection(questions)
        self.topic = FakeTopicCollection(topics)


def make_large_user():
    progress = {
        str(index): {
            "done": True,
            "timestamp": f"2025-01-{(index % 28) + 1:02d}T12:00:00+00:00",
        }
        for index in range(450)
    }
    external_totals = {
        "LeetCode": 320,
        "LeetCode_Easy": 140,
        "LeetCode_Medium": 120,
        "LeetCode_Hard": 60,
        "LeetCode_Rating": 1825,
        "GFG": 80,
        "HackerRank": 55,
        "Coding Ninjas": 35,
        "AtCoder": 20,
    }
    external_daily_counts = {
        f"2025-{month:02d}-{day:02d}": 1
        for month in range(1, 13)
        for day in range(1, 29)
    }
    return {
        "progress": progress,
        "external_totals": external_totals,
        "external_daily_counts": external_daily_counts,
    }


def make_leaderboard_users():
    users = []
    for index in range(250):
        users.append(
            {
                "_id": ObjectId(),
                "name": f"User {index}",
                "college": f"College {index % 8}",
                "profile_photo": "",
                "leetcode_username": f"user-{index}",
                "codingninjas_username": f"cn-{index}",
                "progress": {
                    str(question_id): {
                        "done": question_id % (index % 7 + 2) == 0,
                        "timestamp": f"2025-02-{(question_id % 28) + 1:02d}T08:00:00+00:00",
                    }
                    for question_id in range(180)
                },
                "external_totals": {
                    "LeetCode": 100 + (index % 60),
                    "LeetCode_Easy": 40 + (index % 20),
                    "LeetCode_Medium": 30 + (index % 15),
                    "LeetCode_Hard": 10 + (index % 10),
                    "LeetCode_Rating": 1400 + index,
                    "GFG": 20 + (index % 10),
                    "HackerRank": 10 + (index % 8),
                    "Coding Ninjas": 8 + (index % 6),
                },
                "external_daily_counts": {
                    f"2025-03-{day:02d}": 1 for day in range(1, 21)
                },
            }
        )
    return users


def make_questions():
    urls = [
        "https://leetcode.com/problems/sample/",
        "https://www.geeksforgeeks.org/problems/sample/",
        "https://www.naukri.com/code360/problems/sample/",
        "https://www.hackerrank.com/challenges/sample/",
    ]
    return [{"_id": str(index), "url": urls[index % len(urls)]} for index in range(450)]


def make_search_fixture():
    topics = [
        {"_id": f"topic-{index}", "name": f"Topic {index}", "position": index}
        for index in range(50)
    ]
    questions = [
        {
            "_id": f"q-{index}",
            "problem": f"Binary Search Variant {index}",
            "topic": topics[index % len(topics)]["_id"],
            "url": "https://leetcode.com/problems/binary-search/",
            "url2": "https://practice.geeksforgeeks.org/problems/binary-search/",
            "score": 10 - (index % 5),
        }
        for index in range(200)
    ]
    return FakeSearchDB(questions, topics)


def test_compute_c_score_stays_fast_for_large_progress_documents():
    user = make_large_user()

    compute_c_score(user)
    start = perf_counter()
    for _ in range(10):
        compute_c_score(user)
    elapsed = perf_counter() - start

    assert elapsed < 0.35, f"compute_c_score took {elapsed:.3f}s for 10 large runs"


def test_build_leaderboard_data_stays_within_runtime_budget(monkeypatch):
    fake_db = FakeLeaderboardDB(make_leaderboard_users(), make_questions())
    monkeypatch.setattr("app.leaderboard.service.db", fake_db)

    build_leaderboard_data()
    start = perf_counter()
    for _ in range(3):
        entries = build_leaderboard_data()
    elapsed = perf_counter() - start

    assert len(entries) == 250
    assert elapsed < 1.1, f"build_leaderboard_data took {elapsed:.3f}s for 3 large runs"


def test_search_dsa_questions_stays_fast_for_representative_result_sets():
    fake_db = make_search_fixture()

    search_dsa_questions("binary search", limit=40, db_handle=fake_db)
    start = perf_counter()
    for _ in range(5):
        payload = search_dsa_questions("binary search", limit=40, db_handle=fake_db)
    elapsed = perf_counter() - start

    assert len(payload["results"]) == 40
    assert elapsed < 0.4, f"search_dsa_questions took {elapsed:.3f}s for 5 representative runs"
