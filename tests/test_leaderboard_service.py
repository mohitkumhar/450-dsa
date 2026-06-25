from bson.objectid import ObjectId

from app.leaderboard.service import (
    build_college_leaderboard_data,
    build_leaderboard_data,
    get_user_rank_by_c_score,
)


class FakeCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    def find(self, *args, **kwargs):
        return list(self.documents)


class FakeDB:
    def __init__(self, users, questions):
        self.user = FakeCollection(users)
        self.question = FakeCollection(questions)


def test_build_leaderboard_data_skips_blank_names(monkeypatch):
    users = [
        {
            "_id": ObjectId(),
            "name": "Alice",
            "college": "A College",
            "profile_photo": "alice.png",
            "leetcode_username": "alice-lc",
            "codingninjas_username": "alice-cn",
        },
        {
            "_id": ObjectId(),
            "name": "   ",
            "college": "Ignored College",
        },
    ]
    fake_db = FakeDB(users, [{"url": "https://leetcode.com/problems/two-sum"}])

    monkeypatch.setattr("app.leaderboard.service.db", fake_db)
    monkeypatch.setattr(
        "app.leaderboard.service.compute_c_score",
        lambda user, all_questions=None: {
            "c_score": 123,
            "dsa_done": 12,
            "lc_total": 8,
            "lc_easy": 4,
            "lc_medium": 3,
            "lc_hard": 1,
            "lc_rating": 1600,
            "gfg_total": 2,
            "hr_total": 1,
            "cn_total": 1,
            "active_days": 7,
            "total_solved": 15,
        },
    )

    entries = build_leaderboard_data()

    assert len(entries) == 1
    assert entries[0]["name"] == "Alice"
    assert entries[0]["college"] == "A College"
    assert entries[0]["leetcode_username"] == "alice-lc"
    assert entries[0]["codingninjas_username"] == "alice-cn"
    assert entries[0]["c_score"] == 123


def test_build_college_leaderboard_data_aggregates_and_sorts():
    entries = [
        {
            "user_id": "1",
            "name": "Alice",
            "college": "Alpha University",
            "profile_photo": "alice.png",
            "c_score": 120,
            "total_solved": 50,
            "dsa_done": 25,
            "lc_total": 20,
            "gfg_total": 10,
            "cn_total": 5,
            "hr_total": 2,
            "lc_rating": 1800,
        },
        {
            "user_id": "2",
            "name": "Bob",
            "college": "Alpha University",
            "profile_photo": "bob.png",
            "c_score": 100,
            "total_solved": 45,
            "dsa_done": 20,
            "lc_total": 18,
            "gfg_total": 8,
            "cn_total": 4,
            "hr_total": 1,
            "lc_rating": 0,
        },
        {
            "user_id": "3",
            "name": "Cara",
            "college": "Beta Institute",
            "profile_photo": "cara.png",
            "c_score": 150,
            "total_solved": 40,
            "dsa_done": 18,
            "lc_total": 15,
            "gfg_total": 6,
            "cn_total": 3,
            "hr_total": 2,
            "lc_rating": 1700,
        },
        {
            "user_id": "4",
            "name": "No College",
            "college": "   ",
            "profile_photo": "",
            "c_score": 999,
            "total_solved": 999,
            "dsa_done": 999,
            "lc_total": 999,
            "gfg_total": 999,
            "cn_total": 999,
            "hr_total": 999,
            "lc_rating": 2500,
        },
    ]

    college_entries = build_college_leaderboard_data(entries)

    assert [entry["college"] for entry in college_entries] == [
        "Alpha University",
        "Beta Institute",
    ]

    alpha = college_entries[0]
    assert alpha["member_count"] == 2
    assert alpha["c_score"] == 220
    assert alpha["total_solved"] == 95
    assert alpha["lc_rating"] == 1800
    assert alpha["top_user"] == {
        "name": "Alice",
        "c_score": 120,
        "profile_photo": "alice.png",
    }
    assert alpha["name"] == "Alpha University"
    assert alpha["user_id"] == ""

    beta = college_entries[1]
    assert beta["member_count"] == 1
    assert beta["lc_rating"] == 1700


def test_get_user_rank_by_c_score_uses_sorted_c_score_order():
    entries = [
        {"user_id": "u1", "c_score": 90, "total_solved": 40},
        {"user_id": "u2", "c_score": 140, "total_solved": 25},
        {"user_id": "u3", "c_score": 110, "total_solved": 60},
    ]

    assert get_user_rank_by_c_score("u2", entries) == 1
    assert get_user_rank_by_c_score("u3", entries) == 2
    assert get_user_rank_by_c_score("u1", entries) == 3
    assert get_user_rank_by_c_score("missing", entries) is None
