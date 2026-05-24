from app import _question_platform_updates
from app.utils import compute_user_platforms


def test_question_platform_updates_derives_primary_and_secondary_platforms():
    updates = _question_platform_updates(
        {
            "url": "https://leetcode.com/problems/two-sum/",
            "url2": "https://practice.geeksforgeeks.org/problems/two-sum/1",
        }
    )

    assert updates == {
        "primary_platform": "LeetCode",
        "secondary_platform": "GFG",
    }


def test_compute_user_platforms_prefers_denormalized_primary_platform():
    solved_items = {"q1": {"done": True}}
    all_questions = [
        {
            "_id": "q1",
            "url": "https://example.com/not-a-platform",
            "primary_platform": "Coding Ninjas",
        }
    ]

    platforms = compute_user_platforms(solved_items, {}, all_questions)

    assert platforms["Coding Ninjas"] == 1
    assert platforms["Other"] == 0
