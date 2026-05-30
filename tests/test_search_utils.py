import app.utils as utils


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs
        self.sort_args = None
        self.limit_count = None

    def sort(self, args):
        self.sort_args = args
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
        self.cursor = None

    def find(self, query, projection):
        self.find_calls.append((query, projection))
        self.cursor = FakeCursor(self.docs)
        return self.cursor


class FakeTopicCollection:
    def __init__(self, docs):
        self.docs = docs
        self.find_calls = []

    def find(self, query, projection):
        self.find_calls.append((query, projection))
        requested_ids = set(query.get("_id", {}).get("$in", []))
        return [doc for doc in self.docs if doc["_id"] in requested_ids]


class FakeDB:
    def __init__(self, questions=None, topics=None):
        self.question = FakeQuestionCollection(questions or [])
        self.topic = FakeTopicCollection(topics or [])


def test_search_uses_mongodb_text_search_and_score_sort(monkeypatch):
    fake_db = FakeDB(
        questions=[
            {
                "_id": "q1",
                "problem": "Two Sum",
                "topic": "arrays",
                "url": "https://leetcode.com/problems/two-sum/",
                "url2": "",
                "score": 4.5,
            }
        ],
        topics=[{"_id": "arrays", "name": "Arrays", "position": 1}],
    )
    monkeypatch.setattr(utils, "db", fake_db)

    payload = utils.search_dsa_questions("two sum", limit=10)

    assert fake_db.question.find_calls == [
        (
            {"$text": {"$search": "two sum"}},
            {
                "problem": 1,
                "topic": 1,
                "url": 1,
                "url2": 1,
                "editorial_links": 1,
                "score": {"$meta": "textScore"},
            },
        )
    ]
    assert fake_db.question.cursor.sort_args == [("score", {"$meta": "textScore"})]
    assert fake_db.question.cursor.limit_count == 10
    assert payload["results"][0]["score"] == 4.5


def test_search_preserves_topic_names_and_platform_links(monkeypatch):
    fake_db = FakeDB(
        questions=[
            {
                "_id": "q1",
                "problem": "Merge Intervals",
                "topic": "intervals",
                "url": "https://leetcode.com/problems/merge-intervals/",
                "url2": "https://practice.geeksforgeeks.org/problems/overlapping-intervals/",
                "score": 2.25,
            }
        ],
        topics=[{"_id": "intervals", "name": "Intervals", "position": 7}],
    )
    monkeypatch.setattr(utils, "db", fake_db)

    result = utils.search_dsa_questions("merge intervals")["results"][0]

    assert result["topic"] == "Intervals"
    assert result["topic_id"] == "intervals"
    assert result["topic_position"] == 7
    assert result["links"] == [
        {
            "platform": "LeetCode",
            "url": "https://leetcode.com/problems/merge-intervals/",
            "color": "lc",
        },
        {
            "platform": "GFG",
            "url": "https://practice.geeksforgeeks.org/problems/overlapping-intervals/",
            "color": "gfg",
        },
    ]


def test_search_includes_valid_editorial_links(monkeypatch):
    fake_db = FakeDB(
        questions=[
            {
                "_id": "q1",
                "problem": "Merge Intervals",
                "topic": "intervals",
                "url": "https://leetcode.com/problems/merge-intervals/",
                "url2": "",
                "editorial_links": [
                    {"label": "Official Editorial", "url": "https://leetcode.com/problems/merge-intervals/editorial/"},
                    {"label": "Bad", "url": "javascript:alert(1)"},
                ],
                "score": 2.25,
            }
        ],
        topics=[{"_id": "intervals", "name": "Intervals", "position": 7}],
    )
    monkeypatch.setattr(utils, "db", fake_db)

    result = utils.search_dsa_questions("merge intervals")["results"][0]

    assert result["editorial_links"] == [
        {
            "label": "Official Editorial",
            "url": "https://leetcode.com/problems/merge-intervals/editorial/",
        }
    ]


def test_search_filters_requested_platform_without_extra_collection_scan(monkeypatch):
    fake_db = FakeDB(
        questions=[
            {
                "_id": "q1",
                "problem": "Binary Tree Paths",
                "topic": "trees",
                "url": "https://leetcode.com/problems/binary-tree-paths/",
                "url2": "",
                "score": 3.0,
            },
            {
                "_id": "q2",
                "problem": "Binary Tree Traversal",
                "topic": "trees",
                "url": "https://practice.geeksforgeeks.org/problems/tree-traversal/",
                "url2": "",
                "score": 2.5,
            },
        ],
        topics=[{"_id": "trees", "name": "Trees", "position": 4}],
    )
    monkeypatch.setattr(utils, "db", fake_db)

    payload = utils.search_dsa_questions("gfg binary tree")

    assert payload["requested_platforms"] == ["GFG"]
    assert [result["id"] for result in payload["results"]] == ["q2"]
    assert fake_db.question.find_calls[0][0] == {"$text": {"$search": "binary tree"}}
    assert fake_db.topic.find_calls == [
        ({"_id": {"$in": ["trees"]}}, {"name": 1, "position": 1})
    ]


def test_search_applies_platform_filter_before_final_limit(monkeypatch):
    lc_questions = [
        {
            "_id": f"lc-{index}",
            "problem": f"Binary Tree Variant {index}",
            "topic": "trees",
            "url": f"https://leetcode.com/problems/binary-tree-variant-{index}/",
            "url2": "",
            "score": 100 - index,
        }
        for index in range(40)
    ]
    gfg_question = {
        "_id": "gfg-1",
        "problem": "Binary Tree Traversal",
        "topic": "trees",
        "url": "https://practice.geeksforgeeks.org/problems/binary-tree-traversal/",
        "url2": "",
        "score": 10,
    }
    fake_db = FakeDB(
        questions=lc_questions + [gfg_question],
        topics=[{"_id": "trees", "name": "Trees", "position": 4}],
    )
    monkeypatch.setattr(utils, "db", fake_db)

    payload = utils.search_dsa_questions("gfg binary tree", limit=10)

    assert payload["requested_platforms"] == ["GFG"]
    assert [result["id"] for result in payload["results"]] == ["gfg-1"]
    assert fake_db.question.cursor.limit_count is None
    assert fake_db.topic.find_calls == [
        ({"_id": {"$in": ["trees"]}}, {"name": 1, "position": 1})
    ]


def test_empty_query_returns_without_database_calls(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(utils, "db", fake_db)

    payload = utils.search_dsa_questions("   leetcode   ")

    assert payload == {
        "query": "",
        "requested_platforms": ["LeetCode"],
        "results": [],
        "external_searches": [],
    }
    assert fake_db.question.find_calls == []
    assert fake_db.topic.find_calls == []
