import json
from io import BytesIO
from bson import ObjectId

import app.tracker.routes as tracker_routes
from conftest import build_test_app, csrf_headers, login_test_user
from progress_import import parse_csv_backup, parse_json_backup, process_dry_run


def test_parse_csv_backup():
    csv_data = (
        "Topic,Problem,Done,Bookmarked,Notes,Difficulty,URL,URL2\n"
        "Arrays,Two Sum,True,False,Use a hash map.,Medium,https://leetcode.com/problems/two-sum/,\n"
        "Arrays,Reverse the array,False,True,,Easy,https://www.geeksforgeeks.org/write-a-program-to-reverse-an-array-or-string/,\n"
    )
    items, err = parse_csv_backup(csv_data)
    assert err is None
    assert len(items) == 2
    assert items[0]["problem"] == "Two Sum"
    assert items[0]["done"] is True
    assert items[0]["bookmark"] is False
    assert items[0]["notes"] == "Use a hash map."
    assert items[0]["url"] == "https://leetcode.com/problems/two-sum/"

    assert items[1]["problem"] == "Reverse the array"
    assert items[1]["done"] is False
    assert items[1]["bookmark"] is True
    assert items[1]["notes"] == ""


def test_parse_json_backup():
    json_data = json.dumps({
        "version": "1.0",
        "progress": [
            {
                "topic": "Arrays",
                "problem": "Two Sum",
                "done": True,
                "bookmark": False,
                "notes": "Use a hash map.",
                "url": "https://leetcode.com/problems/two-sum/",
                "url2": ""
            }
        ]
    })
    items, err = parse_json_backup(json_data)
    assert err is None
    assert len(items) == 1
    assert items[0]["problem"] == "Two Sum"
    assert items[0]["done"] is True
    assert items[0]["notes"] == "Use a hash map."


def test_process_dry_run():
    db_questions = [
        {"_id": ObjectId("60c72b2f9b1d8b2e1c8d3e41"), "problem": "Two Sum", "url": "https://leetcode.com/problems/two-sum/", "url2": ""},
        {"_id": ObjectId("60c72b2f9b1d8b2e1c8d3e42"), "problem": "Reverse the array", "url": "https://www.geeksforgeeks.org/write-a-program-to-reverse-an-array-or-string/", "url2": ""}
    ]
    parsed_items = [
        {"problem": "Two Sum", "url": "https://leetcode.com/problems/two-sum/", "url2": "", "done": True, "bookmark": False, "skipped": False, "notes": "HashMap solution"},
        {"problem": "Nonexistent Problem", "url": "https://example.com", "url2": "", "done": True, "bookmark": False, "skipped": False, "notes": ""}
    ]
    current_progress = {
        "60c72b2f9b1d8b2e1c8d3e41": {"done": False, "bookmark": False, "notes": ""}
    }

    summary, changes, conflicts, mapped_progress = process_dry_run(parsed_items, db_questions, current_progress)

    assert summary["total_records"] == 2
    assert summary["matched_records"] == 1
    assert summary["unmatched_records"] == 1
    assert summary["changes_detected"] == 1
    assert summary["conflicts_detected"] == 0

    assert "60c72b2f9b1d8b2e1c8d3e41" in mapped_progress
    assert mapped_progress["60c72b2f9b1d8b2e1c8d3e41"]["done"] is True
    assert mapped_progress["60c72b2f9b1d8b2e1c8d3e41"]["notes"] == "HashMap solution"


def test_export_json_route(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_id = test_db.question.insert_one({
        "topic": topic_id,
        "problem": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "url2": ""
    }).inserted_id

    progress = {
        str(question_id): {"done": True, "bookmark": True, "notes": "Good notes"}
    }
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": progress, "is_admin": False}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/export/json")

    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == "attachment; filename=progress_backup.json"
    
    data = json.loads(response.data)
    assert data["version"] == "1.0"
    assert len(data["progress"]) == 1
    assert data["progress"][0]["problem"] == "Two Sum"
    assert data["progress"][0]["done"] is True
    assert data["progress"][0]["notes"] == "Good notes"


def test_import_preview_route(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    test_db.question.insert_one({
        "topic": topic_id,
        "problem": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "url2": ""
    })

    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": {}, "is_admin": False}).inserted_id

    csv_content = (
        "Topic,Problem,Done,Bookmarked,Notes,Difficulty,URL,URL2\n"
        "Arrays,Two Sum,True,False,Use a hash map.,Medium,https://leetcode.com/problems/two-sum/,\n"
    )

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        data = {
            "file": (BytesIO(csv_content.encode("utf-8")), "backup.csv")
        }
        response = client.post("/progress/import/preview", data=data, content_type="multipart/form-data", headers=csrf_headers(client))

    assert response.status_code == 200
    res_json = response.get_json()
    assert res_json["success"] is True
    assert res_json["summary"]["matched_records"] == 1
    assert len(res_json["changes"]) == 1


def test_import_commit_route_merge(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_id = test_db.question.insert_one({
        "topic": topic_id,
        "problem": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "url2": ""
    }).inserted_id

    # Existing progress: only bookmarked, with notes
    user_id = test_db.user.insert_one({
        "email": "user@example.com",
        "progress": {
            str(question_id): {"done": False, "bookmark": True, "notes": "Existing notes"}
        },
        "in_sheet_platform_counts": {"LeetCode": 0},
        "is_admin": False
    }).inserted_id

    # Import backup: done is True, different notes
    csv_content = (
        "Topic,Problem,Done,Bookmarked,Notes,Difficulty,URL,URL2\n"
        "Arrays,Two Sum,True,False,Imported notes,Medium,https://leetcode.com/problems/two-sum/,\n"
    )

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        data = {
            "file": (BytesIO(csv_content.encode("utf-8")), "backup.csv"),
            "mode": "merge"
        }
        response = client.post("/progress/import/commit", data=data, content_type="multipart/form-data", headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True

    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"][str(question_id)]
    assert progress["done"] is True
    assert progress["bookmark"] is True  # Keep existing bookmark status
    assert "Existing notes" in progress["notes"]
    assert "Imported notes" in progress["notes"]
    assert user["in_sheet_platform_counts"]["LeetCode"] == 1
    # Regression: import commit must update computed stats
    assert user["dsa_progress"] == 100.0
    assert user["current_streak"] >= 1
    assert user["longest_streak"] >= 1


def test_import_commit_route_replace(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))
    topic_id = test_db.topic.insert_one({"name": "Arrays", "position": 1}).inserted_id
    question_id = test_db.question.insert_one({
        "topic": topic_id,
        "problem": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "url2": ""
    }).inserted_id
    untouched_id = test_db.question.insert_one({
        "topic": topic_id,
        "problem": "Best Time to Buy and Sell Stock",
        "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/",
        "url2": ""
    }).inserted_id

    # Existing progress
    user_id = test_db.user.insert_one({
        "email": "user@example.com",
        "progress": {
            str(question_id): {"done": False, "bookmark": True, "notes": "Existing notes"},
            str(untouched_id): {"done": True, "bookmark": False, "notes": "Keep me"}
        },
        "in_sheet_platform_counts": {"LeetCode": 0},
        "is_admin": False
    }).inserted_id

    # Import backup: done is True, bookmark is False, different notes
    csv_content = (
        "Topic,Problem,Done,Bookmarked,Notes,Difficulty,URL,URL2\n"
        "Arrays,Two Sum,True,False,Imported notes,Medium,https://leetcode.com/problems/two-sum/,\n"
    )

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        data = {
            "file": (BytesIO(csv_content.encode("utf-8")), "backup.csv"),
            "mode": "replace"
        }
        response = client.post("/progress/import/commit", data=data, content_type="multipart/form-data", headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.get_json()["success"] is True

    user = test_db.user.find_one({"_id": user_id})
    progress = user["progress"][str(question_id)]
    assert progress["done"] is True
    assert progress["bookmark"] is False  # Bookmark overwritten to False
    assert progress["notes"] == "Imported notes"  # Notes replaced

    # Replace mode should not drop unrelated existing entries that were not in the import file.
    untouched_progress = user["progress"][str(untouched_id)]
    assert untouched_progress["done"] is True
    assert untouched_progress["notes"] == "Keep me"
    # Preserve existing done entries, so counts reflect both solved questions.
    assert user["in_sheet_platform_counts"]["LeetCode"] == 2
    # Regression: import commit must update computed stats
    assert user["dsa_progress"] == 100.0
    assert user["current_streak"] >= 1
    assert user["longest_streak"] >= 1
