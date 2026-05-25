import re
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
INLINE_HANDLER_RE = re.compile(
    r"\bon(?:click|change|error|mouseover|mouseout|input|submit|load)\s*=",
    re.IGNORECASE,
)
TEMPLATES_UNDER_TEST = ("base.html", "profile.html", "topic.html")


def test_key_templates_do_not_use_inline_event_handlers():
    violations = []

    for template_name in TEMPLATES_UNDER_TEST:
        template_path = TEMPLATE_DIR / template_name
        template = template_path.read_text(encoding="utf-8")
        for match in INLINE_HANDLER_RE.finditer(template):
            line_number = template.count("\n", 0, match.start()) + 1
            violations.append(f"{template_name}:{line_number}")

    assert violations == []
