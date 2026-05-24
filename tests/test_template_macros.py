from pathlib import Path


TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
TOPIC_TEMPLATE = TEMPLATES_DIR / "topic.html"
BOOKMARKS_TEMPLATE = TEMPLATES_DIR / "bookmarks.html"
PROFILE_TEMPLATE = TEMPLATES_DIR / "profile.html"
MACROS_TEMPLATE = TEMPLATES_DIR / "macros" / "ui_bits.html"


def test_ui_bits_macro_file_exists_with_shared_macros():
    template = MACROS_TEMPLATE.read_text(encoding="utf-8")

    assert "{% macro question_link_badge" in template
    assert "{% macro award_badge" in template


def test_topic_and_bookmarks_import_question_link_badge_macro():
    topic = TOPIC_TEMPLATE.read_text(encoding="utf-8")
    bookmarks = BOOKMARKS_TEMPLATE.read_text(encoding="utf-8")

    assert '{% from "macros/ui_bits.html" import question_link_badge %}' in topic
    assert '{{ question_link_badge(q.url, p1) }}' in topic
    assert '{{ question_link_badge(q.url2, p2) }}' in topic

    assert '{% from "macros/ui_bits.html" import question_link_badge %}' in bookmarks
    assert "question_link_badge(q.url, q.url|platform_name" in bookmarks
    assert "question_link_badge(q.url2, q.url2|platform_name" in bookmarks


def test_profile_uses_shared_award_badge_macro():
    profile = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert '{% from "macros/ui_bits.html" import award_badge %}' in profile
    assert "{{ award_badge(" in profile
    assert "LeetCode Contestant" in profile
    assert "100 Active Days" in profile
