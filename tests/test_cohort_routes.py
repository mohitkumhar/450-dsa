from datetime import datetime
from bson import ObjectId

import app.cohort.routes as cohort_routes
from conftest import build_test_app, csrf_headers, login_test_user


def test_cohort_index_anonymous(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    with flask_app.test_client() as client:
        response = client.get("/cohorts")
    assert response.status_code == 302
    assert "login" in response.headers["Location"]


def test_cohort_index_empty(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.get("/cohorts")
    assert response.status_code == 200
    assert b"No Cohorts Joined Yet" in response.data


def test_create_cohort_success(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post(
            "/cohorts/create",
            data={"name": "Test Cohort"},
            headers=csrf_headers(client)
        )
    # Should redirect to cohort detail page
    assert response.status_code == 302
    cohort = test_db.cohort.find_one({"name": "Test Cohort"})
    assert cohort is not None
    assert cohort["created_by"] == user_id
    assert len(cohort["join_code"]) == 6

    # Verify creator is a member
    membership = test_db.cohort_membership.find_one({
        "cohort_id": cohort["_id"],
        "user_id": user_id
    })
    assert membership is not None


def test_create_cohort_empty_name(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(
            "/cohorts/create",
            data={"name": "   "},
            headers=csrf_headers(client)
        )
    assert response.status_code == 302
    assert test_db.cohort.count_documents({}) == 0


def test_join_cohort_success(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    
    # Create cohort by another user
    other_user_id = ObjectId()
    cohort_id = test_db.cohort.insert_one({
        "name": "Friend Group",
        "join_code": "XYZ123",
        "created_by": other_user_id
    }).inserted_id

    with flask_app.test_client() as client:
        my_user_id = login_test_user(client, test_db)
        response = client.post(
            "/cohorts/join",
            data={"join_code": "xyz123"}, # test case insensitivity and strip
            headers=csrf_headers(client)
        )

    assert response.status_code == 302
    # Verify my membership
    membership = test_db.cohort_membership.find_one({
        "cohort_id": cohort_id,
        "user_id": my_user_id
    })
    assert membership is not None


def test_join_cohort_invalid_code(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post(
            "/cohorts/join",
            data={"join_code": "WRONG1"},
            headers=csrf_headers(client)
        )
    assert response.status_code == 302
    assert test_db.cohort_membership.count_documents({}) == 0


def test_join_cohort_already_member(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    cohort_id = test_db.cohort.insert_one({
        "name": "Friend Group",
        "join_code": "XYZ123",
        "created_by": ObjectId()
    }).inserted_id

    with flask_app.test_client() as client:
        my_user_id = login_test_user(client, test_db)
        # Already member
        test_db.cohort_membership.insert_one({
            "cohort_id": cohort_id,
            "user_id": my_user_id
        })
        response = client.post(
            "/cohorts/join",
            data={"join_code": "XYZ123"},
            headers=csrf_headers(client)
        )
    assert response.status_code == 302
    assert test_db.cohort_membership.count_documents({"cohort_id": cohort_id}) == 1


def test_cohort_detail_access_denied(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    cohort_id = test_db.cohort.insert_one({
        "name": "Private Group",
        "join_code": "XYZ123",
        "created_by": ObjectId()
    }).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.get(f"/cohorts/{cohort_id}")
    
    assert response.status_code == 302  # redirects to cohorts index
    # Check flash message redirect
    assert "cohorts" in response.headers["Location"]


def test_cohort_detail_success(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(cohort_routes,))
    cohort_id = test_db.cohort.insert_one({
        "name": "Group Leaderboard",
        "join_code": "XYZ123",
        "created_by": ObjectId(),
        "created_at": datetime.now()
    }).inserted_id

    # Create cohort members with progress
    user1_id = test_db.user.insert_one({
        "name": "Member A",
        "email": "a@example.com",
        "progress": {},
        "is_admin": False
    }).inserted_id
    user2_id = test_db.user.insert_one({
        "name": "Member B",
        "email": "b@example.com",
        "progress": {},
        "is_admin": False
    }).inserted_id

    test_db.cohort_membership.insert_many([
        {"cohort_id": cohort_id, "user_id": user1_id},
        {"cohort_id": cohort_id, "user_id": user2_id}
    ])

    with flask_app.test_client() as client:
        login_test_user(client, user1_id)
        response = client.get(f"/cohorts/{cohort_id}")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Group Leaderboard" in html
    assert "Member A" in html
    assert "Member B" in html
