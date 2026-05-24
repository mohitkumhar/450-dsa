from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def read_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def test_base_template_defines_shared_button_utility_classes():
    base = read_template("base.html")

    assert ".ui-btn {" in base
    assert ".ui-btn--primary {" in base
    assert ".ui-btn--secondary {" in base
    assert ".ui-btn--danger {" in base
    assert ".ui-btn--icon {" in base
    assert ".ui-btn--pill {" in base


def test_base_topbar_uses_button_utilities():
    base = read_template("base.html")

    assert 'class="pill-btn ui-btn ui-btn--pill ui-btn--secondary"' in base
    assert 'class="pill-btn accent ui-btn ui-btn--pill ui-btn--primary"' in base
    assert 'class="icon-btn ui-btn ui-btn--icon ui-btn--secondary"' in base


def test_topic_and_bookmarks_reuse_secondary_icon_and_pill_button_utilities():
    topic = read_template("topic.html")
    bookmarks = read_template("bookmarks.html")

    assert 'class="back-btn ui-btn ui-btn--secondary"' in topic
    assert 'class="export-notes-btn ui-btn ui-btn--secondary"' in topic
    assert "filter-btn ui-btn ui-btn--pill ui-btn--secondary" in topic
    assert 'class="action-icon ui-btn ui-btn--icon ui-btn--secondary bookmark-btn' in topic
    assert 'class="notes-btn-sm ui-btn ui-btn--secondary' in topic
    assert 'class="back-btn ui-btn ui-btn--secondary"' in bookmarks
    assert 'class="action-icon ui-btn ui-btn--icon ui-btn--secondary bookmark-btn"' in bookmarks
    assert 'class="notes-btn-sm ui-btn ui-btn--secondary' in bookmarks


def test_profile_reuses_primary_secondary_and_danger_button_utilities():
    profile = read_template("profile.html")

    assert 'class="card-btn ui-btn ui-btn--primary"' in profile
    assert 'class="card-btn ui-btn ui-btn--secondary"' in profile
    assert 'class="ui-btn ui-btn--danger"' in profile
    assert 'class="add-btn ui-btn ui-btn--secondary"' in profile
