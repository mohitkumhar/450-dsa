from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
README = PROJECT_ROOT / "README.md"


def test_pyproject_enables_ruff_import_sorting():
    config = PYPROJECT.read_text(encoding="utf-8")

    assert '[tool.ruff.lint]' in config
    assert 'extend-select = ["I"]' in config
    assert '[tool.ruff.lint.isort]' in config
    assert 'known-first-party = ["app", "tests"]' in config


def test_readme_documents_import_sorting_command():
    readme = README.read_text(encoding="utf-8")

    assert "## Import Sorting" in readme
    assert "ruff check . --select I --fix" in readme
