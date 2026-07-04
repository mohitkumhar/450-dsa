from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def test_external_link_badge_macro_is_shared_across_templates():
    macros = (TEMPLATE_DIR / "_macros.html").read_text(encoding="utf-8")
    topic = (TEMPLATE_DIR / "topic.html").read_text(encoding="utf-8")
    bookmarks = (TEMPLATE_DIR / "bookmarks.html").read_text(encoding="utf-8")
    profile = (TEMPLATE_DIR / "profile.html").read_text(encoding="utf-8")
    search = (TEMPLATE_DIR / "search.html").read_text(encoding="utf-8")

    assert "macro external_link_badge(" in macros
    assert "rel=\"noopener noreferrer\"" in macros

    assert "{% from \"_macros.html\" import external_link_badge %}" in topic
    assert "external_link_badge(q.url, p1" in topic
    assert "external_link_badge(editorial.url, editorial.label" in topic

    assert "{% from \"_macros.html\" import external_link_badge %}" in bookmarks
    assert "external_link_badge(q.url, q1" in bookmarks
    assert "external_link_badge(q.url2, q2" in bookmarks

    assert "{% from \"_macros.html\" import modal_shell, external_link_badge %}" in profile
    assert "external_link_badge(user.hackerrank_username | platform_url('hackerrank'), 'HackerRank'" in profile
    assert "external_link_badge(user.github_username | platform_url('github'), 'GitHub'" in profile

    assert "{% from \"_macros.html\" import external_link_badge %}" in search
    assert "badgeMarkupTemplate" in search
    assert "renderExternalBadge({" in search
