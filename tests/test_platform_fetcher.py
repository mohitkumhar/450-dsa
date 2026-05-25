import time
from unittest.mock import MagicMock, patch

from platform_fetcher import run_fetch_jobs
from app.platforms.fetchers import clear_platform_fetch_cache, fetch_atcoder, fetch_github


def setup_function():
    clear_platform_fetch_cache()


def test_fetch_atcoder_returns_total_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'count': 42}

    with patch('app.platforms.fetchers.requests.get', return_value=mock_response):
        result = fetch_atcoder('tourist')

    assert result == {'total': 42}


def test_fetch_atcoder_returns_empty_on_non_200():
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch('app.platforms.fetchers.requests.get', return_value=mock_response):
        result = fetch_atcoder('unknown_user')

    assert result == {}


def test_fetch_atcoder_returns_empty_on_exception():
    with patch('app.platforms.fetchers.requests.get', side_effect=Exception('timeout')):
        result = fetch_atcoder('tourist')

    assert result == {}


def test_fetch_atcoder_caches_successful_results():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'count': 42}

    with patch('app.platforms.fetchers.requests.get', return_value=mock_response) as mock_get:
        first = fetch_atcoder('tourist')
        second = fetch_atcoder('tourist')

    assert first == {'total': 42}
    assert second == {'total': 42}
    assert mock_get.call_count == 1


def test_fetch_atcoder_caches_failed_results():
    with patch('app.platforms.fetchers.requests.get', side_effect=Exception('timeout')) as mock_get:
        first = fetch_atcoder('tourist')
        second = fetch_atcoder('tourist')

    assert first == {}
    assert second == {}
    assert mock_get.call_count == 1


def test_fetch_github_cache_is_keyed_by_username():
    contribution_a = MagicMock()
    contribution_a.text = "3 contributions on 2026-05-24"
    issues_a = MagicMock()
    issues_a.json.return_value = {"total_count": 2}
    prs_a = MagicMock()
    prs_a.json.return_value = {"total_count": 5}
    merged_a = MagicMock()
    merged_a.json.return_value = {"total_count": 1}
    commits_a = MagicMock()
    commits_a.json.return_value = {"total_count": 8}

    contribution_b = MagicMock()
    contribution_b.text = "1 contributions on 2026-05-24"
    issues_b = MagicMock()
    issues_b.json.return_value = {"total_count": 7}
    prs_b = MagicMock()
    prs_b.json.return_value = {"total_count": 9}
    merged_b = MagicMock()
    merged_b.json.return_value = {"total_count": 4}
    commits_b = MagicMock()
    commits_b.json.return_value = {"total_count": 11}

    with patch(
        'app.platforms.fetchers.requests.get',
        side_effect=[
            contribution_a, issues_a, prs_a, merged_a, commits_a,
            contribution_b, issues_b, prs_b, merged_b, commits_b,
        ],
    ) as mock_get:
        first = fetch_github('octocat')
        second = fetch_github('octocat')
        third = fetch_github('hubot')

    assert first == second
    assert first != third
    assert mock_get.call_count == 10


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
