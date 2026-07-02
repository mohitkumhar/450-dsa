from pathlib import Path


TOPIC_JS = Path(__file__).resolve().parents[1] / "static" / "js" / "topic.js"


def test_topic_page_keyboard_shortcuts_are_wired():
    script = TOPIC_JS.read_text(encoding="utf-8")

    assert 'event.key === "j"' in script
    assert 'event.key === "k"' in script
    assert 'event.key === "b"' in script
    assert 'event.key === "n"' in script
    assert 'event.key === "?"' in script
    assert 'event.key === " " || event.key === "Enter"' in script
