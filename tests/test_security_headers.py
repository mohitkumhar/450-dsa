import app.tracker.routes as tracker_routes
from conftest import build_test_app


def test_base_template_does_not_load_blocked_jquery(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))

    with flask_app.test_client() as client:
        response = client.get("/")

    html = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "https://code.jquery.com" not in html


def test_content_security_policy_matches_base_script_origins(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch, extra_db_targets=(tracker_routes,))

    with flask_app.test_client() as client:
        response = client.get("/")

    csp = response.headers["Content-Security-Policy"]
    assert "script-src" in csp
    assert "https://cdn.jsdelivr.net" in csp
    assert "https://unpkg.com" in csp
    assert "https://code.jquery.com" not in csp
