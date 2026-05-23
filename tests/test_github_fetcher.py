import os
from unittest.mock import Mock, patch

from app.platforms.fetchers import fetch_github


def make_response(status_code=200, json_data=None, text=""):
    r = Mock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_data or {}
    return r


@patch("app.platforms.fetchers.requests.get")
def test_fetch_github_success(mock_get):
    mock_get.side_effect = [
        make_response(text="5 contributions on 2024-01-01 No contributions on 2024-01-02"),
        make_response(json_data={"total_count": 3}),
        make_response(json_data={"total_count": 4}),
        make_response(json_data={"total_count": 2}),
        make_response(json_data={"total_count": 10}),
    ]

    with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}, clear=False):
        result = fetch_github("octocat")

    assert "error" not in result
    assert result["stats"] == {"issues": 3, "prs": 4, "merged_prs": 2, "commits": 10}
    assert result["calendar"] == {"2024-01-01": 5, "2024-01-02": 0}


@patch("app.platforms.fetchers.requests.get")
def test_fetch_github_rate_limited_403(mock_get):
    rate_limited = make_response(status_code=403)
    rate_limited.json.side_effect = AssertionError("json() must not be called on 403")
    mock_get.side_effect = [
        make_response(text="2 contributions on 2024-01-01"),
        rate_limited,
    ]

    result = fetch_github("octocat")

    assert result["error"] == "rate_limited"
    assert result["stats"] is None
    assert result["calendar"] == {"2024-01-01": 2}


@patch("app.platforms.fetchers.requests.get")
def test_fetch_github_rate_limited_429(mock_get):
    rate_limited = make_response(status_code=429)
    rate_limited.json.side_effect = AssertionError("json() must not be called on 429")
    mock_get.side_effect = [
        make_response(text="1 contributions on 2024-01-01"),
        rate_limited,
    ]

    result = fetch_github("octocat")

    assert result["error"] == "rate_limited"
    assert result["stats"] is None
    assert result["calendar"] == {"2024-01-01": 1}


@patch("app.platforms.fetchers.requests.get")
def test_fetch_github_no_token(mock_get):
    mock_get.side_effect = [
        make_response(text="7 contributions on 2024-01-03"),
        make_response(json_data={"total_count": 1}),
        make_response(json_data={"total_count": 2}),
        make_response(json_data={"total_count": 3}),
        make_response(json_data={"total_count": 4}),
    ]

    env_without_token = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
    with patch.dict(os.environ, env_without_token, clear=True):
        result = fetch_github("octocat")

    assert "error" not in result
    assert result["stats"] == {"issues": 1, "prs": 2, "merged_prs": 3, "commits": 4}
    for call in mock_get.call_args_list[1:]:
        assert "Authorization" not in call.kwargs.get("headers", {})
