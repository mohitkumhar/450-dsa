from pathlib import Path


LEADERBOARD_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "leaderboard.html"


def test_leaderboard_fetch_checks_api_status_and_entries():
    template = LEADERBOARD_TEMPLATE.read_text(encoding="utf-8")

    assert "if (!response.ok)" in template
    assert "data.error || data.message || `Leaderboard request failed (${response.status})`" in template
    assert "if (!Array.isArray(data.entries))" in template
    assert "Leaderboard response was missing entries." in template


def test_leaderboard_error_state_resets_pagination():
    template = LEADERBOARD_TEMPLATE.read_text(encoding="utf-8")

    assert "function renderLeaderboardError(error)" in template
    assert "currentPage = 1;" in template
    assert "totalPages = 1;" in template
    assert "currentUserRank = null;" in template
    assert "renderPagination();" in template
