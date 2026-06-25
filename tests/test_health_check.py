from conftest import build_test_app


def test_health_check_endpoint_returns_status_and_timestamp(monkeypatch):
    app, _ = build_test_app(monkeypatch)

    with app.test_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "healthy"
    assert isinstance(payload["timestamp"], str)
    assert "T" in payload["timestamp"]


def test_health_check_endpoint_skips_db_initialization(monkeypatch):
    app, _ = build_test_app(monkeypatch)
    app._db_initialized = False

    with app.test_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert app._db_initialized is False
