from pathlib import Path


PROFILE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "profile.html"


def test_profile_template_does_not_use_inline_event_handlers_for_profile_actions():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert 'onclick="showCodelioCard()"' not in template
    assert 'onclick="copyProgressCardUrl()"' not in template
    assert 'onclick="openImportModal()"' not in template
    assert 'onclick="openEditProfile()"' not in template
    assert 'onclick="openDeleteModal()"' not in template
    assert 'onchange="handlePhotoUpload(event)"' not in template
