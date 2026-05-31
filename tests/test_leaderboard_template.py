from pathlib import Path


LEADERBOARD_JS = Path(__file__).resolve().parents[1] / "static" / "js" / "leaderboard.js"


def test_leaderboard_fetch_checks_api_status_and_entries():
    js_content = LEADERBOARD_JS.read_text(encoding="utf-8")

    assert "if (!response.ok)" in js_content
    assert "data.error || data.message || `Leaderboard request failed (${response.status})`" in js_content
    assert "if (!Array.isArray(data.entries))" in js_content
    assert "Leaderboard response was missing entries." in js_content


def test_leaderboard_error_state_resets_pagination():
    js_content = LEADERBOARD_JS.read_text(encoding="utf-8")

    assert "function renderLeaderboardError(error)" in js_content
    assert "currentPage = 1;" in js_content
    assert "totalPages = 1;" in js_content
    assert "currentUserRank = null;" in js_content
    assert "renderPagination();" in js_content


def test_leaderboard_aborts_previous_requests_and_ignores_stale_results():
    js_content = LEADERBOARD_JS.read_text(encoding="utf-8")

    assert "let leaderboardController = null;" in js_content
    assert "if (leaderboardController) leaderboardController.abort();" in js_content
    assert "const controller = new AbortController();" in js_content
    assert "const response = await fetch(url, { signal: controller.signal });" in js_content
    assert "if (leaderboardController !== controller) return;" in js_content
    assert "if (error.name === 'AbortError') return;" in js_content
