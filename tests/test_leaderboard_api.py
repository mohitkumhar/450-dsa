import mongomock
import app as app_module
import app.leaderboard.service as leaderboard_service
from flask import abort

def create_test_app(monkeypatch):
    """Helper to spin up a faked app environment, matching the project's style."""
    test_db = mongomock.MongoClient().db
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    monkeypatch.setattr(app_module, "db", test_db)
    monkeypatch.setattr(leaderboard_service, "db", test_db)

    monkeypatch.setattr(app_module.mongo, "init_app", lambda flask_app, **kwargs: None)
    monkeypatch.setattr(app_module.oauth, "register", lambda *args, **kwargs: None)

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    flask_app._db_initialized = True

    return flask_app, test_db

def test_leaderboard_429_response(monkeypatch):
    """
    Test that when a 429 Too Many Requests error occurs,
    the API safely returns JSON so the frontend parser doesn't crash.
    """
    flask_app, test_db = create_test_app(monkeypatch)

    # 1. THE MAGIC TRICK: We replace the normal data-fetching function with one
    # that instantly triggers a 429. This completely bypasses the sleeping rate limiter!
    def force_rate_limit(*args, **kwargs):
        abort(429, description="Too many requests. Please try again in a moment.")

    monkeypatch.setattr("app.leaderboard.routes.build_leaderboard_data", force_rate_limit)

    # 2. Make exactly ONE request
    with flask_app.test_client() as client:
        response = client.get('/api/leaderboard?mode=cscore&page=1')

        # 3. Verify the response is a 429 and perfectly formatted JSON
        assert response.status_code == 429, "Expected a 429 status code"
        assert response.is_json, "429 response MUST be JSON"

        data = response.get_json()
        assert "error" in data or "message" in data, "429 JSON must contain an error message"
