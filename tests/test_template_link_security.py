import re
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TARGET_BLANK_LINK_RE = re.compile(
    r"<a\b(?=[^>]*\btarget\s*=\s*(['\"])_blank\1)(?P<attrs>[^>]*)>",
    re.IGNORECASE | re.DOTALL,
)
REL_RE = re.compile(r"\brel\s*=\s*(['\"])(?P<value>[^'\"]*)\1", re.IGNORECASE)


def test_external_blank_links_use_noopener_noreferrer():
    missing_rel = []

    for template_path in TEMPLATE_DIR.rglob("*.html"):
        template = template_path.read_text(encoding="utf-8")
        for match in TARGET_BLANK_LINK_RE.finditer(template):
            attrs = match.group("attrs")
            rel_match = REL_RE.search(attrs)
            rel_values = set(rel_match.group("value").lower().split()) if rel_match else set()
            if not {"noopener", "noreferrer"}.issubset(rel_values):
                line_number = template.count("\n", 0, match.start()) + 1
                missing_rel.append(f"{template_path.relative_to(TEMPLATE_DIR)}:{line_number}")

    assert missing_rel == []
