from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def read_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def test_external_link_badge_macro_exists_with_safe_rel_attrs():
    macros = read_template("_macros.html")

    assert "{% macro external_link_badge(" in macros
    assert 'target="_blank"' in macros
    assert 'rel="noopener noreferrer"' in macros


def test_topic_and_bookmarks_use_external_link_badge_macro():
    topic = read_template("topic.html")
    bookmarks = read_template("bookmarks.html")

    assert '{% from "_macros.html" import external_link_badge %}' in topic
    assert "external_link_badge(" in topic
    assert '{% from "_macros.html" import external_link_badge %}' in bookmarks
    assert "external_link_badge(" in bookmarks


def test_profile_platform_links_use_external_link_badge_macro():
    profile = read_template("profile.html")

    assert '{% from "_macros.html" import external_link_badge %}' in profile
    assert 'extra_classes="link-out"' in profile
    assert 'icon_only=True' in profile


def test_search_template_uses_shared_external_link_badge_renderer():
    search = read_template("search.html")

    assert "function renderExternalLinkBadge({" in search
    assert "renderExternalLinkBadge({" in search
