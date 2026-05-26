import time
from unittest.mock import MagicMock, patch

from platform_fetcher import run_fetch_jobs
from app.platforms.fetchers import clear_platform_http_session, fetch_atcoder


def setup_function():
    clear_platform_http_session()


def test_fetch_atcoder_returns_total_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'count': 42}
    fake_session = MagicMock()
    fake_session.get.return_value = mock_response

    with patch('app.platforms.fetchers._get_http_session', return_value=fake_session):
        result = fetch_atcoder('tourist')

    assert result == {'total': 42}


def test_fetch_atcoder_returns_empty_on_non_200():
    mock_response = MagicMock()
    mock_response.status_code = 404
    fake_session = MagicMock()
    fake_session.get.return_value = mock_response

    with patch('app.platforms.fetchers._get_http_session', return_value=fake_session):
        result = fetch_atcoder('unknown_user')

    assert result == {}


def test_fetch_atcoder_returns_empty_on_exception():
    fake_session = MagicMock()
    fake_session.get.side_effect = Exception('timeout')

    with patch('app.platforms.fetchers._get_http_session', return_value=fake_session):
        result = fetch_atcoder('tourist')

    assert result == {}


def test_fetchers_reuse_thread_local_http_session():
    fake_session = MagicMock()
    fake_session.get.return_value = MagicMock(status_code=404)

    with patch('app.platforms.fetchers.requests.Session', return_value=fake_session) as mock_session:
        fetch_atcoder('tourist')
        fetch_atcoder('tourist')

    mock_session.assert_called_once()
    assert fake_session.get.call_count == 2


def test_run_fetch_jobs_executes_jobs_concurrently():
    def slow_result(value):
        time.sleep(0.2)
        return value

    started = time.perf_counter()
    results, errors = run_fetch_jobs({
        'leetcode': lambda: slow_result({'total': 10}),
        'github': lambda: slow_result({'stats': {'prs': 4}}),
        'gfg': lambda: slow_result({'total': 7}),
    })
    elapsed = time.perf_counter() - started

    assert results == {
        'leetcode': {'total': 10},
        'github': {'stats': {'prs': 4}},
        'gfg': {'total': 7},
    }
    assert errors == {}
    assert elapsed < 0.45


def test_run_fetch_jobs_keeps_other_results_when_one_job_fails():
    def failing_job():
        raise RuntimeError('platform unavailable')

    results, errors = run_fetch_jobs({
        'leetcode': lambda: {'total': 10},
        'github': failing_job,
        'gfg': lambda: {'total': 7},
    })

    assert results['leetcode'] == {'total': 10}
    assert results['gfg'] == {'total': 7}
    assert results['github'] is None
    assert errors == {'github': 'platform unavailable'}
