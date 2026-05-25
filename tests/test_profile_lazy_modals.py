from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def test_profile_template_does_not_inline_heavy_profile_modals():
    template = (TEMPLATE_DIR / "profile.html").read_text(encoding="utf-8")

    assert "id=\"syncModal\"" not in template
    assert "id=\"cardModal\"" not in template
    assert "id=\"editProfileModal\"" not in template
    assert "Enter your usernames to sync activity heatmap" not in template
    assert "Start typing to search globally..." not in template


def test_profile_modal_partials_use_shared_modal_macro():
    sync_template = (TEMPLATE_DIR / "profile" / "_sync_modal.html").read_text(encoding="utf-8")
    card_template = (TEMPLATE_DIR / "profile" / "_card_modal.html").read_text(encoding="utf-8")
    edit_template = (TEMPLATE_DIR / "profile" / "_edit_profile_modal.html").read_text(encoding="utf-8")

    for template in (sync_template, card_template, edit_template):
        assert '{% from "_macros.html" import modal_shell %}' in template
        assert template.count("{% call modal_shell(") == 1

    assert "id=\"btnSync\"" in sync_template
    assert "Profile card copied!" in card_template
    assert "id=\"ep_college\"" in edit_template
