from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
MACRO_TEMPLATE = TEMPLATE_DIR / "macros" / "external_link_badges.html"


def test_external_link_badge_macro_exists_with_expected_helpers():
    template = MACRO_TEMPLATE.read_text(encoding="utf-8")

    assert "macro external_link_badge" in template
    assert "macro profile_platform_link" in template
    assert "macro search_badge_template" in template


def test_templates_import_and_use_external_link_badge_macro():
    topic_template = (TEMPLATE_DIR / "topic.html").read_text(encoding="utf-8")
    bookmarks_template = (TEMPLATE_DIR / "bookmarks.html").read_text(encoding="utf-8")
    profile_template = (TEMPLATE_DIR / "profile.html").read_text(encoding="utf-8")
    search_template = (TEMPLATE_DIR / "search.html").read_text(encoding="utf-8")

    assert '{% from "macros/external_link_badges.html" import external_link_badge %}' in topic_template
    assert '{{ external_link_badge(q.url, p1' in topic_template
    assert '{{ external_link_badge(q.url2, p2' in topic_template

    assert '{% from "macros/external_link_badges.html" import external_link_badge %}' in bookmarks_template
    assert '{{ external_link_badge(q.url, q.url|platform_name' in bookmarks_template
    assert '{{ external_link_badge(q.url2, q.url2|platform_name' in bookmarks_template

    assert '{% from "macros/external_link_badges.html" import profile_platform_link %}' in profile_template
    assert "profile_platform_link(" in profile_template

    assert '{% from "macros/external_link_badges.html" import search_badge_template %}' in search_template
    assert "search-badge-template-lc-external" in search_template
    assert "renderBadge(link, 'external'" in search_template
