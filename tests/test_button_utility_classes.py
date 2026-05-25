from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def test_base_template_defines_shared_button_utility_classes():
    template = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")

    assert ".ui-btn {" in template
    assert ".ui-btn-primary {" in template
    assert ".ui-btn-secondary {" in template
    assert ".ui-btn-danger {" in template
    assert ".ui-btn-icon {" in template
    assert ".ui-btn-pill {" in template
    assert ".ui-btn-block {" in template


def test_profile_and_topic_templates_use_button_utilities():
    profile_template = (TEMPLATE_DIR / "profile.html").read_text(encoding="utf-8")
    topic_template = (TEMPLATE_DIR / "topic.html").read_text(encoding="utf-8")
    base_template = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")

    assert "class=\"card-btn ui-btn ui-btn-primary ui-btn-block\"" in profile_template
    assert "class=\"card-btn ui-btn ui-btn-success ui-btn-block\"" in profile_template
    assert "class=\"ui-btn ui-btn-secondary ui-btn-block\"" in profile_template
    assert "class=\"ui-btn ui-btn-danger ui-btn-block\"" in profile_template
    assert "class=\"view-lb-btn ui-btn ui-btn-primary ui-btn-block\"" in profile_template

    assert "class=\"filter-btn ui-btn ui-btn-secondary ui-btn-pill" in topic_template
    assert "class=\"filter-btn ui-btn ui-btn-primary ui-btn-pill\"" in topic_template

    assert "class=\"pill-btn ui-btn ui-btn-secondary ui-btn-pill\"" in base_template
    assert "class=\"pill-btn accent ui-btn ui-btn-primary ui-btn-pill\"" in base_template
    assert "class=\"icon-btn ui-btn ui-btn-secondary ui-btn-icon\"" in base_template
