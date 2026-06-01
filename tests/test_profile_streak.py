from unittest.mock import patch, MagicMock
from app.profile.routes import filter_heatmap_counts


def make_user(progress=None):
    user = MagicMock()
    user.progress = progress or {}
    user.profile_photo = None
    user.name = "Test User"
    user.lc_badges_json = "[]"
    user.hr_badges_json = "[]"
    user.rating_history = []
    user.external_totals = {}
    user.in_sheet_platform_counts = {}
    return user


def test_profile_passes_current_streak_to_template():
    progress = {"q1": {"done": True, "timestamp": None}}
    with patch("app.profile.routes.compute_streak", return_value=(5, 10)) as mock_streak:
        streak, longest = mock_streak(progress)
    assert streak == 5
    assert longest == 10


def test_profile_passes_longest_streak_to_template():
    progress = {}
    with patch("app.profile.routes.compute_streak", return_value=(0, 3)) as mock_streak:
        streak, longest = mock_streak(progress)
    assert streak == 0
    assert longest == 3
