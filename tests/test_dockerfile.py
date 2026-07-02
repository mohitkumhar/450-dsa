from pathlib import Path


def test_dockerfile_starts_gunicorn_from_app_module():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert '"app:app"' in dockerfile
    assert '"run:app"' not in dockerfile
