from pathlib import Path


BASE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "base.html"


def test_page_loading_releases_on_dom_ready_and_fallback_timeout():
    """New behavior: release via DOMContentLoaded / pageshow / 3000 ms fallback."""
    template = BASE_TEMPLATE.read_text(encoding="utf-8")

    # Core guard function must be present
    assert "function releasePageLoading()" in template

    # Must release on DOMContentLoaded (primary trigger)
    assert "document.addEventListener('DOMContentLoaded'" in template

    # Must also release on pageshow (handles bfcache restores)
    assert "window.addEventListener('pageshow', releasePageLoading, { once: true });" in template

    # Fallback timeout must be 3000 ms
    assert "window.setTimeout(releasePageLoading, 3000);" in template

    # idempotency guard must be present
    assert "loadingReleased" in template

    # Early-exit when DOM is already ready
    assert "document.readyState" in template


def test_page_loading_does_not_use_old_behavior():
    """Old behavior (window.releasePageLoading, requestAnimationFrame, load event,
    2500 ms timeout) must NOT appear in the template."""
    template = BASE_TEMPLATE.read_text(encoding="utf-8")

    # Must NOT expose releasePageLoading on window
    assert "window.releasePageLoading" not in template

    # Must NOT use requestAnimationFrame for the loading release
    assert "requestAnimationFrame" not in template

    # Must NOT listen to the 'load' event for releasing the loader
    assert "window.addEventListener('load', releasePageLoading" not in template

    # Must NOT use the old 2500 ms fallback
    assert "setTimeout(releasePageLoading, 2500)" not in template
