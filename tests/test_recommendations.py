from datetime import timedelta
from app.tracker.recommendation import get_next_recommendation
from app.utils import utc_now


class DummyUser:
    def __init__(self, is_authenticated=True, progress=None):
        self.is_authenticated = is_authenticated
        self.progress = progress or {}


def test_recommendation_anonymous():
    # If not authenticated, should return first question of first topic
    user = DummyUser(is_authenticated=False)
    pre = {
        "topics": [{"_id": "t1", "name": "Arrays", "position": 1}],
        "all_questions": [
            {"_id": "q1", "topic": "t1", "problem": "Prob 1", "difficulty": "Easy", "url": "url1", "url2": ""}
        ]
    }
    rec = get_next_recommendation(user, db=None, pre=pre)
    assert rec is not None
    assert rec["reason"] == "Next in Topic"
    assert rec["question"]["_id"] == "q1"


def test_recommendation_new_user():
    # New user with empty progress: should suggest first question of first topic
    user = DummyUser(progress={})
    pre = {
        "topics": [
            {"_id": "t1", "name": "Arrays", "position": 1},
            {"_id": "t2", "name": "Strings", "position": 2}
        ],
        "all_questions": [
            {"_id": "q1", "topic": "t1", "problem": "Prob 1", "difficulty": "Easy", "url": "url1", "url2": ""},
            {"_id": "q2", "topic": "t1", "problem": "Prob 2", "difficulty": "Medium", "url": "url2", "url2": ""},
            {"_id": "q3", "topic": "t2", "problem": "Prob 3", "difficulty": "Easy", "url": "url3", "url2": ""}
        ],
        "topic_lookup": {
            "t1": {"name": "Arrays", "position": 1},
            "t2": {"name": "Strings", "position": 2}
        }
    }
    rec = get_next_recommendation(user, db=None, pre=pre)
    assert rec is not None
    assert rec["reason"] == "Next in Topic"
    assert rec["question"]["_id"] == "q1"


def test_recommendation_due_revision():
    # One easy question completed 31 days ago (due for revision after 30 days)
    # Another medium question completed 10 days ago (due after 14 days, not due yet)
    user = DummyUser(progress={
        "q1": {"done": True, "timestamp": utc_now() - timedelta(days=31)},
        "q2": {"done": True, "timestamp": utc_now() - timedelta(days=10)},
    })
    pre = {
        "topics": [{"_id": "t1", "name": "Arrays", "position": 1}],
        "all_questions": [
            {"_id": "q1", "topic": "t1", "problem": "Easy Prob", "difficulty": "Easy", "url": "url1", "url2": ""},
            {"_id": "q2", "topic": "t1", "problem": "Medium Prob", "difficulty": "Medium", "url": "url2", "url2": ""},
            {"_id": "q3", "topic": "t1", "problem": "Hard Prob", "difficulty": "Hard", "url": "url3", "url2": ""}
        ],
        "topic_lookup": {
            "t1": {"name": "Arrays", "position": 1}
        }
    }
    rec = get_next_recommendation(user, db=None, pre=pre)
    assert rec is not None
    assert rec["reason"] == "Due Revision"
    assert rec["question"]["_id"] == "q1"


def test_recommendation_needs_practice():
    # Skipped question should be recommended as Needs Practice (over Goal Progress or Next in Topic)
    # But NOT over Due Revision
    user = DummyUser(progress={
        "q1": {"done": True, "timestamp": utc_now() - timedelta(days=2)},  # Completed recently, not due
        "q2": {"skipped": True, "done": False},  # Skipped
    })
    pre = {
        "topics": [{"_id": "t1", "name": "Arrays", "position": 1}],
        "all_questions": [
            {"_id": "q1", "topic": "t1", "problem": "Easy Prob", "difficulty": "Easy", "url": "url1", "url2": ""},
            {"_id": "q2", "topic": "t1", "problem": "Medium Prob", "difficulty": "Medium", "url": "url2", "url2": ""},
            {"_id": "q3", "topic": "t1", "problem": "Hard Prob", "difficulty": "Hard", "url": "url3", "url2": ""}
        ],
        "topic_lookup": {
            "t1": {"name": "Arrays", "position": 1}
        }
    }
    rec = get_next_recommendation(user, db=None, pre=pre)
    assert rec is not None
    assert rec["reason"] == "Needs Practice"
    assert rec["question"]["_id"] == "q2"


def test_recommendation_goal_progress():
    # A topic has >= 70% progress.
    # Topic 1 has 3 questions. 2 done, 1 left (66.6% progress - close but not >=70%).
    # Topic 2 has 10 questions. 7 done, 3 left (70% progress - triggers Goal Progress!).
    user = DummyUser(progress={
        "q1": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q4": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q5": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q6": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q7": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q8": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q9": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
        "q10": {"done": True, "timestamp": utc_now() - timedelta(days=1)},
    })
    pre = {
        "topics": [
            {"_id": "t1", "name": "Arrays", "position": 1},
            {"_id": "t2", "name": "Strings", "position": 2}
        ],
        "all_questions": [
            {"_id": "q1", "topic": "t1", "problem": "Prob 1", "difficulty": "Easy"},
            {"_id": "q2", "topic": "t1", "problem": "Prob 2", "difficulty": "Medium"},
            {"_id": "q3", "topic": "t1", "problem": "Prob 3", "difficulty": "Hard"},

            {"_id": "q4", "topic": "t2", "problem": "Prob 4", "difficulty": "Easy"},
            {"_id": "q5", "topic": "t2", "problem": "Prob 5", "difficulty": "Easy"},
            {"_id": "q6", "topic": "t2", "problem": "Prob 6", "difficulty": "Easy"},
            {"_id": "q7", "topic": "t2", "problem": "Prob 7", "difficulty": "Medium"},
            {"_id": "q8", "topic": "t2", "problem": "Prob 8", "difficulty": "Medium"},
            {"_id": "q9", "topic": "t2", "problem": "Prob 9", "difficulty": "Medium"},
            {"_id": "q10", "topic": "t2", "problem": "Prob 10", "difficulty": "Hard"},
            {"_id": "q11", "topic": "t2", "problem": "Prob 11", "difficulty": "Hard"},
            {"_id": "q12", "topic": "t2", "problem": "Prob 12", "difficulty": "Hard"},
            {"_id": "q13", "topic": "t2", "problem": "Prob 13", "difficulty": "Hard"}
        ],
        "topic_lookup": {
            "t1": {"name": "Arrays", "position": 1},
            "t2": {"name": "Strings", "position": 2}
        }
    }
    rec = get_next_recommendation(user, db=None, pre=pre)
    assert rec is not None
    assert rec["reason"] == "Goal Progress"
    assert rec["question"]["_id"] in ["q11", "q12", "q13"]


def test_recommendation_all_completed():
    # User completed all questions: get_next_recommendation returns None
    user = DummyUser(progress={
        "q1": {"done": True, "timestamp": utc_now()},
        "q2": {"done": True, "timestamp": utc_now()}
    })
    pre = {
        "topics": [{"_id": "t1", "name": "Arrays", "position": 1}],
        "all_questions": [
            {"_id": "q1", "topic": "t1", "problem": "Prob 1", "difficulty": "Easy"},
            {"_id": "q2", "topic": "t1", "problem": "Prob 2", "difficulty": "Medium"}
        ]
    }
    rec = get_next_recommendation(user, db=None, pre=pre)
    assert rec is None
