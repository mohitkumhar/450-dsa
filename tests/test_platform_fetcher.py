import time
from unittest.mock import call
from unittest.mock import MagicMock, patch

from platform_fetcher import run_fetch_jobs
from app.platforms.fetchers import build_github_stats_payload, fetch_atcoder, fetch_github


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


def test_build_github_stats_payload_uses_login_variable():
    payload = build_github_stats_payload("octocat")

    assert payload["variables"] == {"login": "octocat"}
    assert "mergedPullRequests" in payload["query"]
    assert "contributionCalendar" in payload["query"]


def test_fetch_github_uses_graphql_when_token_present(monkeypatch):
    graphql_response = MagicMock()
    graphql_response.json.return_value = {
        "data": {
            "user": {
                "issues": {"totalCount": 5},
                "pullRequests": {"totalCount": 6},
                "mergedPullRequests": {"totalCount": 4},
                "contributionsCollection": {
                    "contributionCalendar": {
                        "weeks": [
                            {
                                "contributionDays": [
                                    {"date": "2026-05-24", "contributionCount": 3}
                                ]
                            }
                        ]
                    }
                },
            }
        }
    }
    commits_response = MagicMock()
    commits_response.json.return_value = {"total_count": 9}

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    with patch("app.platforms.fetchers.requests.post", return_value=graphql_response) as mock_post, patch(
        "app.platforms.fetchers.requests.get",
        return_value=commits_response,
    ) as mock_get:
        result = fetch_github("octocat")

    assert result == {
        "calendar": {"2026-05-24": 3},
        "stats": {"issues": 5, "prs": 6, "merged_prs": 4, "commits": 9},
    }
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"
    mock_get.assert_called_once_with(
        "https://api.github.com/search/commits?q=author:octocat",
        headers={
            "Accept": "application/vnd.github.cloak-preview+json",
            "Authorization": "Bearer test-token",
        },
        timeout=5,
    )


def test_fetch_github_falls_back_without_graphql_token(monkeypatch):
    contribution_response = MagicMock()
    contribution_response.text = "3 contributions on 2026-05-24 No contributions on 2026-05-23"
    issues_response = MagicMock()
    issues_response.json.return_value = {"total_count": 2}
    prs_response = MagicMock()
    prs_response.json.return_value = {"total_count": 5}
    merged_response = MagicMock()
    merged_response.json.return_value = {"total_count": 1}
    commits_response = MagicMock()
    commits_response.json.return_value = {"total_count": 8}

    with patch(
        "app.platforms.fetchers.requests.get",
        side_effect=[contribution_response, issues_response, prs_response, merged_response, commits_response],
    ) as mock_get:
        result = fetch_github("octocat")

    assert result == {
        "calendar": {"2026-05-24": 3, "2026-05-23": 0},
        "stats": {"issues": 2, "prs": 5, "merged_prs": 1, "commits": 8},
    }
    assert mock_get.call_args_list == [
        call("https://github.com/users/octocat/contributions", timeout=5),
        call("https://api.github.com/search/issues?q=type:issue+author:octocat", timeout=5),
        call("https://api.github.com/search/issues?q=type:pr+author:octocat", timeout=5),
        call("https://api.github.com/search/issues?q=type:pr+is:merged+author:octocat", timeout=5),
        call(
            "https://api.github.com/search/commits?q=author:octocat",
            headers={"Accept": "application/vnd.github.cloak-preview+json"},
            timeout=5,
        ),
    ]


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
