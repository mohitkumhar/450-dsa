from pathlib import Path


PROFILE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "profile.html"


def test_chart_js_loaded_via_promise_with_load_event():
    """Chart.js must be loaded via a Promise that resolves on the script load
    event — never via fire-and-forget dynamic injection."""
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    # Promise-based loader must exist
    assert "window._chartJsReady = new Promise" in template

    # The primary CDN script must resolve the Promise on 'load'
    assert "s.addEventListener('load'" in template

    # The fallback CDN script must also resolve on 'load'
    assert "fb.addEventListener('load'" in template

    # Fallback must reject when both CDNs fail
    assert "fb.addEventListener('error'" in template

    # The failed primary script tag must be removed before trying fallback
    assert "s.remove()" in template


def test_chart_init_gated_behind_chart_js_ready():
    """All new Chart(...) calls must be inside initCharts(), which is only
    invoked after window._chartJsReady resolves."""
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    # initCharts function must exist
    assert "function initCharts()" in template

    # initCharts must be called only after _chartJsReady resolves
    assert "window._chartJsReady.then(initCharts)" in template

    # Graceful degradation: catch handler must mark chart shells as ready
    # even if Chart.js fails to load entirely
    assert "window._chartJsReady.then(initCharts).catch" in template


def test_no_ungated_chart_instantiation():
    """Old pattern: calling new Chart(...) directly outside initCharts() or
    checking typeof Chart !== 'undefined' as a guard must NOT appear."""
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    # The old typeof Chart guard must not appear
    assert "typeof Chart !== 'undefined'" not in template

    # The old fire-and-forget IIFE and its variable name must not appear
    assert "document.head.appendChild(chartScript)" not in template
    assert "})();" not in template.split("{% block head %}")[1].split("{% endblock %}")[0]


def test_chart_js_loader_in_head_block():
    """The Promise-based Chart.js loader must be in the {% block head %}
    section so it starts loading as early as possible."""
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    head_block = template.split("{% block head %}")[1].split("{% endblock %}")[0]

    assert "window._chartJsReady" in head_block
    assert "cdn.jsdelivr.net/npm/chart.js" in head_block
    assert "unpkg.com/chart.js" in head_block
