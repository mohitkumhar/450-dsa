from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_requirements_exclude_test_only_packages():
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "mongomock==" not in runtime


def test_dev_requirements_extend_runtime_and_include_dev_packages():
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    assert dev.startswith("-r requirements.txt")
    assert "mongomock==" in dev
    assert "pytest==" in dev
    assert "ruff==" in dev
    assert "black==" in dev
