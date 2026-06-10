from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def test_profile_template_marks_primary_avatar_as_eager_and_badges_as_lazy():
    profile = (TEMPLATE_DIR / "profile.html").read_text(encoding="utf-8")
    ui_bits = (TEMPLATE_DIR / "macros" / "ui_bits.html").read_text(encoding="utf-8")

    assert 'src="{{ user.profile_photo }}" width="90" height="90" loading="eager" fetchpriority="high" decoding="async"' in profile
    assert 'src="{{ icon_url }}" width="36" height="36" loading="lazy" decoding="async"' in ui_bits
    assert 'src="{{ user.profile_photo }}" width="80" height="80" loading="lazy" decoding="async"' in profile


def test_public_profile_template_keeps_visible_avatar_eager_with_dimensions():
    template = (TEMPLATE_DIR / "public_profile.html").read_text(encoding="utf-8")

    assert 'src="{{ user.avatar_url }}" width="90" height="90" loading="eager" fetchpriority="high" decoding="async"' in template
