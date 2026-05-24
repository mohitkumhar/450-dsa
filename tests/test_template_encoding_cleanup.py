from pathlib import Path


TEMPLATE_PATHS = [
    Path("templates/base.html"),
    Path("templates/topic.html"),
    Path("templates/leaderboard.html"),
]


def test_cleaned_templates_use_ascii_only():
    for path in TEMPLATE_PATHS:
        contents = path.read_text(encoding="utf-8")
        assert contents.isascii(), f"{path} still contains non-ASCII characters"
