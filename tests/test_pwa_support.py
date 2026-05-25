import json
from pathlib import Path

from tests.conftest import build_test_app


def test_manifest_contains_expected_pwa_metadata(monkeypatch):
    app, _ = build_test_app(monkeypatch)

    with app.test_client() as client:
        response = client.get("/static/manifest.webmanifest")

    assert response.status_code == 200
    manifest = json.loads(response.get_data(as_text=True))
    assert manifest["name"] == "450 DSA Tracker"
    assert manifest["short_name"] == "450 DSA"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#111111"
    assert manifest["background_color"] == "#111111"
    assert len(manifest["icons"]) >= 2


def test_base_template_links_manifest_icons_and_pwa_script():
    template_path = Path(__file__).resolve().parents[1] / "templates" / "base.html"
    html = template_path.read_text(encoding="utf-8")

    assert 'rel="manifest"' in html
    assert "manifest.webmanifest" in html
    assert "icon-192.svg" in html
    assert "icon-512.svg" in html
    assert "js/pwa-install.js" in html


def test_install_script_registers_root_service_worker_with_app_scope():
    script_path = Path(__file__).resolve().parents[1] / "static" / "js" / "pwa-install.js"
    script = script_path.read_text(encoding="utf-8")

    assert 'register("/service-worker.js", { scope: "/" })' in script


def test_offline_shell_and_service_worker_are_served(monkeypatch):
    app, _ = build_test_app(monkeypatch)

    with app.test_client() as client:
        offline_response = client.get("/static/offline.html")
        worker_response = client.get("/service-worker.js")

    assert offline_response.status_code == 200
    assert b"You\xe2\x80\x99re offline" in offline_response.data
    assert worker_response.status_code == 200
    assert worker_response.mimetype == "application/javascript"
    assert b"fetch(request)" in worker_response.data
    assert b"offline.html" in worker_response.data
