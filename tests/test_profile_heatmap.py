from datetime import date, timedelta

from app.profile.routes import HEATMAP_DAYS, filter_heatmap_counts


def test_filter_heatmap_counts_keeps_only_rendered_window():
    today = date(2026, 5, 26)
    first_visible = today - timedelta(days=HEATMAP_DAYS - 1)
    counts = {
        (first_visible - timedelta(days=1)).isoformat(): 9,
        first_visible.isoformat(): 2,
        today.isoformat(): 5,
        (today + timedelta(days=1)).isoformat(): 7,
    }

    assert filter_heatmap_counts(counts, today=today) == {
        first_visible.isoformat(): 2,
        today.isoformat(): 5,
    }
