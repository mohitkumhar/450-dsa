from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_TEMPLATE = REPO_ROOT / "templates" / "profile.html"
CHART_LOADER = REPO_ROOT / "static" / "js" / "chart_loader.js"


def test_profile_template_uses_lazy_chart_loader_helper():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert "cdn.jsdelivr.net/npm/chart.js" not in template
    assert "unpkg.com/chart.js@4/dist/chart.umd.js" not in template
    assert """<script src="{{ url_for('static', filename='js/chart_loader.js') }}" defer></script>""" in template
    assert "ChartCtor = await window.loadChartJs();" in template
    assert "renderProfileCharts();" in template


def test_chart_loader_keeps_cdn_fallback_and_reuses_single_promise():
    loader = CHART_LOADER.read_text(encoding="utf-8")

    assert '"https://cdn.jsdelivr.net/npm/chart.js"' in loader
    assert '"https://unpkg.com/chart.js@4/dist/chart.umd.js"' in loader
    assert "window.loadChartJs = function () {" in loader
    assert "if (!chartJsPromise)" in loader
    assert "return Promise.resolve(window.Chart);" in loader
