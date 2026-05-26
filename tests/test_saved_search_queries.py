import app.search.routes as search_routes
from conftest import build_test_app, login_test_user


def test_search_page_embeds_saved_searches_for_authenticated_user(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(search_routes,))
    user_id = test_db.user.insert_one(
        {
            "email": "user@example.com",
            "progress": {},
            "is_admin": False,
            "saved_searches": [{"id": "saved-1", "name": "DP Medium", "query": "dp medium"}],
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.get("/search")

    html = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "DP Medium" in html
    assert "dp medium" in html


def test_create_saved_search_persists_to_current_user(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(search_routes,))

    with flask_app.test_client() as client:
        user_id = login_test_user(client, test_db)
        response = client.post("/api/saved_searches", json={"name": "Graph Prep", "query": "gfg graph"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["saved_searches"][0]["name"] == "Graph Prep"
    assert body["saved_searches"][0]["query"] == "gfg graph"

    user = test_db.user.find_one({"_id": user_id})
    assert user["saved_searches"][0]["name"] == "Graph Prep"


def test_rename_and_delete_saved_search(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(search_routes,))
    user_id = test_db.user.insert_one(
        {
            "email": "user@example.com",
            "progress": {},
            "is_admin": False,
            "saved_searches": [{"id": "saved-1", "name": "Old Name", "query": "arrays"}],
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        rename_response = client.patch("/api/saved_searches/saved-1", json={"name": "New Name"})
        delete_response = client.delete("/api/saved_searches/saved-1")

    assert rename_response.status_code == 200
    assert rename_response.get_json()["saved_searches"][0]["name"] == "New Name"
    assert delete_response.status_code == 200
    assert delete_response.get_json()["saved_searches"] == []


def test_saved_search_requires_query(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch, extra_db_targets=(search_routes,))

    with flask_app.test_client() as client:
        login_test_user(client, test_db)
        response = client.post("/api/saved_searches", json={"name": "Empty", "query": "   "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "query is required"
