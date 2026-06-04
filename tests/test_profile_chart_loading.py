import re
from pathlib import Path

import app.leaderboard.service as leaderboard_service
import app.profile.routes as profile_routes
from conftest import build_test_app, login_test_user


PROFILE_TEMPLATE = Path("templates/profile.html").read_text(encoding="utf-8")
PROFILE_JS = Path("static/js/profile.js").read_text(encoding="utf-8")


def test_profile_does_not_eager_load_chartjs_in_head():
    head = PROFILE_TEMPLATE.split("{% block content %}", 1)[0]

    assert "cdn.jsdelivr.net/npm/chart.js" not in head
    assert "unpkg.com/chart.js" not in head


def test_profile_lazy_loads_charts_on_intersection():
    assert "function loadChartJs()" in PROFILE_JS
    assert "new IntersectionObserver" in PROFILE_JS
    assert "renderProfileCharts()" in PROFILE_JS
