from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def test_modal_macro_exists_and_defines_notes_modal():
    template = (TEMPLATE_DIR / "macros" / "modals.html").read_text(encoding="utf-8")

    assert "macro notes_modal" in template
    assert 'class="app-modal"' in template
    assert 'class="app-modal__dialog"' in template
    assert 'class="app-modal__actions"' in template


def test_base_template_defines_shared_modal_classes():
    stylesheet = (STATIC_DIR / "css" / "main.css").read_text(encoding="utf-8")

    assert ".app-modal {" in stylesheet
    assert ".app-modal.open {" in stylesheet
    assert ".app-modal__dialog {" in stylesheet
    assert ".app-modal__title {" in stylesheet
    assert ".app-modal__textarea {" in stylesheet
    assert ".app-modal__actions {" in stylesheet


def test_topic_and_bookmarks_use_shared_notes_modal_macro():
    topic_template = (TEMPLATE_DIR / "topic.html").read_text(encoding="utf-8")
    bookmarks_template = (TEMPLATE_DIR / "bookmarks.html").read_text(encoding="utf-8")

    assert '{% from "macros/modals.html" import notes_modal %}' in topic_template
    assert '{% from "macros/modals.html" import notes_modal %}' in bookmarks_template

    assert "{{ notes_modal(textarea_label='Notes for this question') }}" in topic_template
    assert "{{ notes_modal(textarea_label='Notes') }}" in bookmarks_template

    assert "modal-overlay" not in topic_template
    assert "modal-ov" not in bookmarks_template
