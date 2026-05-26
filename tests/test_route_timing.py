import json

import app as app_module

from conftest import build_test_app


def test_route_timing_targets_cover_key_profile_leaderboard_search_routes():
    assert {
        "profile.profile",
        "profile.sync_platforms",
        "leaderboard.leaderboard",
        "leaderboard.api_leaderboard",
        "search.search",
        "search.api_search_questions",
        "tracker.export_csv",
        "tracker.export_notes",
    } <= app_module.ROUTE_TIMING_ENDPOINTS


def test_instrumented_search_route_logs_structured_timing(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)
    records = []

    monkeypatch.setattr(
        flask_app.logger,
        "info",
        lambda message, payload: records.append((message, payload)),
    )

    response = flask_app.test_client().get("/search?q=graphs")

    assert response.status_code == 200
    assert len(records) == 1

    message, payload = records[0]
    data = json.loads(payload)

    assert message == "route_timing %s"
    assert data["endpoint"] == "search.search"
    assert data["method"] == "GET"
    assert data["route"] == "/search"
    assert data["status_code"] == 200
    assert isinstance(data["duration_ms"], float)
    assert data["duration_ms"] >= 0


def test_non_instrumented_route_does_not_emit_timing_log(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)
    records = []

    monkeypatch.setattr(
        flask_app.logger,
        "info",
        lambda message, payload: records.append((message, payload)),
    )

    response = flask_app.test_client().get("/faq")

    assert response.status_code == 200
    assert records == []
