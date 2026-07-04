from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def test_base_template_defines_shared_button_utility_classes():
    stylesheet = (STATIC_DIR / "css" / "main.css").read_text(encoding="utf-8")

    assert "background-color: var(--bg-primary) !important;" in stylesheet
    assert "--text-muted: #8a8a8a;" in stylesheet
    assert ".ui-btn {" in stylesheet
    assert ".ui-btn-primary {" in stylesheet
    assert ".ui-btn-secondary {" in stylesheet
    assert ".ui-btn-danger {" in stylesheet
    assert ".ui-btn-icon {" in stylesheet
    assert ".ui-btn-pill {" in stylesheet
    assert ".ui-btn-block {" in stylesheet


def test_profile_cards_use_theme_safe_surfaces():
    stylesheet = (STATIC_DIR / "css" / "profile.css").read_text(encoding="utf-8")

    assert ".rank-card{background:var(--bg-card);" in stylesheet
    assert ".award-badge{width:64px;height:74px;background:var(--bg-secondary);" in stylesheet
    assert ".chart-shell .chart-skeleton{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;border-radius:12px;background:var(--bg-card-hover);" in stylesheet
    assert ".profile-card-shell{background:var(--bg-card);" in stylesheet
    assert ".profile-card-share-btn{width:100%;margin-top:14px;padding:10px;background:var(--accent);" in stylesheet


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


def test_app_styles_load_after_bootstrap_for_theme_overrides():
    base_template = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")

    assert base_template.index("bootstrap.min.css") < base_template.index("css/main.css")
