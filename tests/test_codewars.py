from unittest.mock import MagicMock, patch

from app.platforms.fetchers import clear_platform_http_session, fetch_codewars


def setup_function():
    clear_platform_http_session()


def test_fetch_codewars_returns_total_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "username": "g964",
        "honor": 500,
        "ranks": {"overall": {"name": "4 kyu", "color": "blue"}},
        "codeChallenges": {"totalCompleted": 120},
    }
    fake_session = MagicMock()
    fake_session.get.return_value = mock_response

    with patch("app.platforms.fetchers._get_http_session", return_value=fake_session):
        result = fetch_codewars("g964")

    assert result == {"total": 120, "honor": 500, "rank": "4 kyu"}
    fake_session.get.assert_called_once()
    call_args = fake_session.get.call_args
    assert "codewars.com/api/v1/users/g964" in call_args[0][0]


def test_fetch_codewars_returns_empty_on_non_200():
    mock_response = MagicMock()
    mock_response.status_code = 404
    fake_session = MagicMock()
    fake_session.get.return_value = mock_response

    with patch("app.platforms.fetchers._get_http_session", return_value=fake_session):
        result = fetch_codewars("nonexistent_user_xyz")

    assert result == {}


def test_fetch_codewars_returns_empty_on_timeout():
    fake_session = MagicMock()
    fake_session.get.side_effect = Exception("Connection timed out")

    with patch("app.platforms.fetchers._get_http_session", return_value=fake_session):
        result = fetch_codewars("g964")

    assert result == {}


def test_fetch_codewars_handles_missing_fields():
    """API returns 200 but with partial/empty data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "username": "newuser",
        "honor": 0,
        "ranks": {},
        "codeChallenges": {},
    }
    fake_session = MagicMock()
    fake_session.get.return_value = mock_response

    with patch("app.platforms.fetchers._get_http_session", return_value=fake_session):
        result = fetch_codewars("newuser")

    assert result == {"total": 0, "honor": 0, "rank": ""}


def test_fetch_codewars_in_sync_pipeline():
    """Codewars job is registered by build_platform_sync_jobs."""
    from app.profile.sync_service import build_platform_sync_jobs

    jobs = build_platform_sync_jobs(codewars_username="g964")
    assert "codewars" in jobs

    jobs_empty = build_platform_sync_jobs(codewars_username="")
    assert "codewars" not in jobs_empty
