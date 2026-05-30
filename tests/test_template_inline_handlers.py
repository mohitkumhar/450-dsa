import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "templates" / "base.html",
    ROOT / "templates" / "topic.html",
    ROOT / "templates" / "profile.html",
    ROOT / "templates" / "_macros.html",
]
INLINE_HANDLER_RE = re.compile(r"\bon(?:click|mouseover|mouseout|change|error)\s*=", re.IGNORECASE)


def test_cleanup_templates_do_not_use_inline_event_handlers():
    offenders = []

    for file_path in FILES:
        template = file_path.read_text(encoding="utf-8")
        for match in INLINE_HANDLER_RE.finditer(template):
            line_number = template.count("\n", 0, match.start()) + 1
            offenders.append(f"{file_path.name}:{line_number}")

    assert offenders == []
