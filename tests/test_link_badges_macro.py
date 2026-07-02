from pathlib import Path


TOPIC_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "topic.html"
BOOKMARKS_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "bookmarks.html"
MACRO_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "macros" / "link_badges.html"


def test_link_badges_macro_is_shared_by_topic_and_bookmarks_templates():
    macro = MACRO_TEMPLATE.read_text(encoding="utf-8")
    topic = TOPIC_TEMPLATE.read_text(encoding="utf-8")
    bookmarks = BOOKMARKS_TEMPLATE.read_text(encoding="utf-8")

    assert "macro external_link_badge" in macro
    assert "external_link_badge(" in topic
    assert "external_link_badge(" in bookmarks
    assert "badge-link" in macro
