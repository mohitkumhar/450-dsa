from pathlib import Path


BASE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "base.html"


def test_page_loading_releases_on_dom_ready_and_fallback_timeout():
    template = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert "function releasePageLoading()" in template
    assert "document.addEventListener('DOMContentLoaded'" in template
    assert "window.addEventListener('pageshow', releasePageLoading, { once: true });" in template
    assert "window.setTimeout(releasePageLoading, 3000);" in template
    assert "window.addEventListener('load', releasePageLoading, { once: true });" not in template
