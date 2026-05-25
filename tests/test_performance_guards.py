import time
from datetime import datetime, timedelta, timezone

from app.leaderboard.service import build_leaderboard_data
from app.search.service import search_dsa_questions
from app.utils import compute_c_score


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)
        self.limit_count = None

    def sort(self, _args):
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
        if "$text" not in query:
            return list(self.docs)
        return FakeCursor(self.docs)


class FakeTopicCollection:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, query, projection):
        requested_ids = set(query.get("_id", {}).get("$in", []))
        return [doc for doc in self.docs if doc["_id"] in requested_ids]


class FakeUserCollection:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, *_args, **_kwargs):
        return list(self.docs)


class FakeLeaderboardDB:
    def __init__(self, users, questions):
        self.user = FakeUserCollection(users)
        self.question = FakeQuestionCollection(questions)


class FakeSearchDB:
    def __init__(self, questions, topics):
        self.question = FakeQuestionCollection(questions)
        self.topic = FakeTopicCollection(topics)


def make_progress(count):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        f"q{index}": {
            "done": True,
            "timestamp": base + timedelta(days=index % 90),
        }
        for index in range(count)
    }


def make_external_daily_counts(count):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        (start + timedelta(days=index)).strftime("%Y-%m-%d"): 1
        for index in range(count)
    }


def make_user(index, solved_count=180):
    return {
        "_id": f"user-{index}",
        "name": f"User {index}",
        "college": f"College {index % 12}",
        "profile_photo": "",
        "leetcode_username": f"user{index}-lc",
        "codingninjas_username": f"user{index}-cn",
        "progress": make_progress(solved_count),
        "external_totals": {
            "LeetCode": 220 + (index % 40),
            "LeetCode_Easy": 110,
            "LeetCode_Medium": 80,
            "LeetCode_Hard": 30,
            "LeetCode_Rating": 1500 + index,
            "GFG": 40,
            "HackerRank": 15,
            "Coding Ninjas": 20,
        },
        "external_daily_counts": make_external_daily_counts(120),
    }


def make_questions(count=450):
    topics = ["arrays", "trees", "graphs", "dp", "math"]
    return [
        {
            "_id": f"q{index}",
            "problem": f"Problem {index}",
            "topic": topics[index % len(topics)],
            "url": f"https://leetcode.com/problems/problem-{index}/",
            "url2": "",
            "score": float(count - index),
        }
        for index in range(count)
    ]


def test_compute_c_score_stays_fast_for_representative_user():
    user = make_user(1, solved_count=260)

    started = time.perf_counter()
    for _ in range(120):
        result = compute_c_score(user)
    elapsed = time.perf_counter() - started

    assert result["c_score"] > 0
    assert elapsed < 0.8


def test_build_leaderboard_data_handles_representative_dataset_quickly(monkeypatch):
    users = [make_user(index) for index in range(90)]
    questions = [{"url": question["url"]} for question in make_questions()]
    monkeypatch.setattr("app.leaderboard.service.db", FakeLeaderboardDB(users, questions))

    started = time.perf_counter()
    entries = build_leaderboard_data()
    elapsed = time.perf_counter() - started

    assert len(entries) == 90
    assert elapsed < 1.0


def test_search_dsa_questions_stays_within_generous_runtime_budget():
    topics = [
        {"_id": "arrays", "name": "Arrays", "position": 1},
        {"_id": "trees", "name": "Trees", "position": 2},
        {"_id": "graphs", "name": "Graphs", "position": 3},
        {"_id": "dp", "name": "Dynamic Programming", "position": 4},
        {"_id": "math", "name": "Math", "position": 5},
    ]
    fake_db = FakeSearchDB(make_questions(220), topics)

    started = time.perf_counter()
    payload = search_dsa_questions("problem", limit=80, db_handle=fake_db)
    elapsed = time.perf_counter() - started

    assert len(payload["results"]) == 80
    assert elapsed < 0.35
