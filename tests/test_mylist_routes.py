"""Tests for the My List blueprint (app/mylist/routes.py)."""
import app.mylist.routes as mylist_routes
import app.tracker.routes as tracker_routes
from conftest import build_test_app, csrf_headers, login_test_user


def _setup(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(tracker_routes, mylist_routes),
    )
    user_id = test_db.user.insert_one({
        "email": "a@example.com",
        "name": "A",
        "progress": {},
        "is_admin": False,
        "external_daily_counts": {},
        "external_totals": {},
    }).inserted_id
    other_id = test_db.user.insert_one({
        "email": "b@example.com",
        "name": "B",
        "progress": {},
        "is_admin": False,
        "external_daily_counts": {},
        "external_totals": {},
    }).inserted_id
    return flask_app, test_db, user_id, other_id


def test_add_question(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={
        "title": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "category": "Arrays",
        "difficulty": "Easy",
        "notes": "Use a hashmap",
    }, headers=csrf_headers(client))
    assert r.status_code == 201
    data = r.get_json()
    assert data["success"] is True
    assert "id" in data
    assert test_db.user_questions.count_documents({}) == 1


def test_add_question_requires_title(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={"title": "", "difficulty": "Easy"},
                    headers=csrf_headers(client))
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_add_question_invalid_difficulty(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={"title": "X", "difficulty": "Extreme"},
                    headers=csrf_headers(client))
    assert r.status_code == 400


def test_update_question(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={"title": "Two Sum", "difficulty": "Easy"},
                    headers=csrf_headers(client))
    qid = r.get_json()["id"]
    r2 = client.patch(f"/mylist/{qid}", json={"done": True, "difficulty": "Hard"},
                      headers=csrf_headers(client))
    assert r2.status_code == 200
    assert r2.get_json()["success"] is True
    doc = test_db.user_questions.find_one({})
    assert doc["done"] is True
    assert doc["difficulty"] == "Hard"


def test_toggle_done(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={"title": "Q", "difficulty": "Medium"},
                    headers=csrf_headers(client))
    qid = r.get_json()["id"]
    client.patch(f"/mylist/{qid}", json={"done": True}, headers=csrf_headers(client))
    doc = test_db.user_questions.find_one({})
    assert doc["done"] is True
    client.patch(f"/mylist/{qid}", json={"done": False}, headers=csrf_headers(client))
    doc = test_db.user_questions.find_one({})
    assert doc["done"] is False


def test_delete_question(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={"title": "Q", "difficulty": "Easy"},
                    headers=csrf_headers(client))
    qid = r.get_json()["id"]
    r2 = client.delete(f"/mylist/{qid}", headers=csrf_headers(client))
    assert r2.status_code == 200
    assert r2.get_json()["success"] is True
    assert test_db.user_questions.count_documents({}) == 0


def test_ownership_isolation(monkeypatch):
    flask_app, test_db, user_id, other_id = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add", json={"title": "Q", "difficulty": "Easy"},
                    headers=csrf_headers(client))
    qid = r.get_json()["id"]
    login_test_user(client, other_id)
    r2 = client.delete(f"/mylist/{qid}", headers=csrf_headers(client))
    assert r2.status_code == 404
    assert test_db.user_questions.count_documents({}) == 1


def test_unauthenticated_add_redirects(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    r = client.post("/mylist/add", json={"title": "Q", "difficulty": "Easy"},
                    headers=csrf_headers(client))
    assert r.status_code in (302, 401, 403)


def test_csrf_rejection(monkeypatch):
    flask_app, test_db, user_id, _ = _setup(monkeypatch)
    client = flask_app.test_client()
    login_test_user(client, user_id)
    r = client.post("/mylist/add",
                    data='{"title":"Q","difficulty":"Easy"}',
                    content_type="application/json")
    assert r.status_code in (400, 403)
