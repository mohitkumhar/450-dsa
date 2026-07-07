from conftest import build_test_app, csrf_headers, login_test_user
from profile_validation import build_profile_updates


def test_profile_updates_trim_text_and_accept_https_urls():
    updates, error = build_profile_updates({
        'name': '  Saurabh  ',
        'bio': 'Building AI systems',
        'website_url': 'https://example.com/portfolio',
    })

    assert error is None
    assert updates == {
        'name': 'Saurabh',
        'bio': 'Building AI systems',
        'website_url': 'https://example.com/portfolio',
    }


def test_profile_updates_reject_blank_name():
    updates, error = build_profile_updates({'name': '   '})

    assert updates is None
    assert error == 'name is required'


def test_profile_updates_reject_overlong_text():
    updates, error = build_profile_updates({'bio': 'x' * 501})

    assert updates is None
    assert error == 'bio must be at most 500 characters'


def test_profile_updates_reject_javascript_urls():
    updates, error = build_profile_updates({'linkedin_url': 'javascript:alert(1)'})

    assert updates is None
    assert error == 'Invalid URL for linkedin_url'


def test_profile_updates_reject_non_text_values():
    updates, error = build_profile_updates({'headline': {'nested': 'value'}})

    assert updates is None
    assert error == 'headline must be text'
def test_profile_updates_accept_valid_profile_visibility():
    updates, error = build_profile_updates({"profile_visibility": "stats_only"})

    assert error is None
    assert updates == {"profile_visibility": "stats_only"}


def test_profile_updates_normalize_profile_visibility():
    updates, error = build_profile_updates({"profile_visibility": "  PRIVATE  "})

    assert error is None
    assert updates == {"profile_visibility": "private"}


def test_profile_updates_reject_invalid_profile_visibility():
    updates, error = build_profile_updates({"profile_visibility": "friends_only"})

    assert updates is None
    assert error == "profile_visibility must be one of: public, private, stats_only"


def test_profile_updates_accepts_new_display_preferences():
    updates, error = build_profile_updates({
        "accent_color": "#123abc",
        "compact_mode": True,
        "chart_palette": "cool",
    })

    assert error is None
    assert updates == {
        "accent_color": "#123abc",
        "compact_mode": True,
        "chart_palette": "cool",
    }


def test_profile_updates_rejects_invalid_accent_color():
    updates, error = build_profile_updates({"accent_color": "blue"})

    assert updates is None
    assert error == "accent_color must be a valid hex color"


def test_profile_updates_rejects_invalid_chart_palette():
    updates, error = build_profile_updates({"chart_palette": "rainbow"})

    assert updates is None
    assert error == "chart_palette must be one of: default, cool, warm, monochrome"


def test_edit_profile_rejects_missing_json_body(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": {}}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post("/edit_profile", headers=csrf_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }


def test_edit_profile_rejects_malformed_json(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": {}}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post(
            "/edit_profile",
            data="{not-json",
            content_type="application/json",
            headers=csrf_headers(client),
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Request body must be a JSON object."


def test_edit_profile_rejects_json_array(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": {}}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post("/edit_profile", json=["name"], headers=csrf_headers(client))

    assert response.status_code == 400
    assert response.get_json()["error"] == "Request body must be a JSON object."


def test_edit_profile_updates_display_preferences(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    user_id = test_db.user.insert_one({"email": "user@example.com", "progress": {}, "profile_visibility": "public"}).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post(
            "/edit_profile",
            json={
                "accent_color": "#1a2b3c",
                "compact_mode": True,
                "chart_palette": "warm",
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    updated_user = test_db.user.find_one({"_id": user_id})
    assert updated_user["accent_color"] == "#1a2b3c"
    assert updated_user["compact_mode"] is True
    assert updated_user["chart_palette"] == "warm"
