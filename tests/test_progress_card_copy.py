from pathlib import Path


PROFILE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "profile.html"


def test_progress_card_copy_handles_clipboard_rejection():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert "navigator.clipboard.writeText(url).then" in template
    assert ".catch(() =>" in template
    assert "showProgressCardUrlFallback(url)" in template


def test_progress_card_copy_fallback_exposes_readonly_url_field():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert 'id="progress-card-copy-fallback"' in template
    assert 'id="progress-card-copy-url"' in template
    assert 'aria-label="Progress image URL"' in template
    assert "input.select()" in template


def test_profile_template_uses_shared_toast_and_button_busy_helpers():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert "window.setButtonBusyState(" in template
    assert "window.setIconBusyState(" in template
    assert 'id="toast"' not in template
    assert "function showToast(msg)" not in template


def test_profile_template_uses_shared_modal_macro():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert '{% from "_macros.html" import modal_shell %}' in template
    assert template.count("{% call modal_shell(") == 3


def test_profile_card_modal_uses_theme_safe_surface_and_real_copy_action():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert 'class="profile-card-shell"' in template
    assert 'class="profile-card-stats"' in template
    assert 'class="profile-card-stat"' in template
    assert 'class="profile-card-share-btn"' in template
    assert "copyProfileCardUrl()" in template
    assert "showToast('Profile card copied! 📋')" not in template
    assert "background:linear-gradient(135deg,#1a1a2e,#16213e)" not in template
