from flask import Flask

from app.profile.routes import profile_bp


def create_profile_test_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True, SECRET_KEY="test-secret")
    app.register_blueprint(profile_bp)
    return app


def test_sync_platforms_rejects_missing_json_body():
    app = create_profile_test_app()

    response = app.test_client().post("/sync_platforms")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }


def test_sync_platforms_rejects_malformed_json_body():
    app = create_profile_test_app()

    response = app.test_client().post(
        "/sync_platforms",
        data="{bad json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }


def test_sync_platforms_rejects_non_object_json_body():
    app = create_profile_test_app()

    response = app.test_client().post("/sync_platforms", json=["leetcode"])

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }
