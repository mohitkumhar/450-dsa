from pathlib import Path


def test_dockerfile_starts_gunicorn_from_run_module():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert '"run:app"' in dockerfile
    assert '"app:app"' not in dockerfile
