import os
from unittest.mock import Mock, patch

from app.platforms.fetchers import fetch_github


def make_response(status_code=200, json_data=None, text=""):
    r = Mock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_data or {}
    return r


def set_session_responses(mock_session_factory, get_responses=None, post_responses=None):
    fake_session = Mock()
    if get_responses is not None:
        fake_session.get.side_effect = get_responses
    if post_responses is not None:
        fake_session.post.side_effect = post_responses
    mock_session_factory.return_value = fake_session
    return fake_session


@patch("app.platforms.fetchers._get_http_session")
def test_fetch_github_success(mock_session_factory):
    fake_session = set_session_responses(mock_session_factory, [
        make_response(text="5 contributions on 2024-01-01 No contributions on 2024-01-02"),
    ], [
        make_response(json_data={
            "data": {
                "issues": {"totalCount": 3},
                "prs": {"totalCount": 4},
                "mergedPrs": {"totalCount": 2},
                "commits": {"totalCount": 10},
            }
        }),
    ])

    with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}, clear=False):
        result = fetch_github("octocat")

    assert "error" not in result
    assert result["stats"] == {"issues": 3, "prs": 4, "merged_prs": 2, "commits": 10}
    assert result["calendar"] == {"2024-01-01": 5, "2024-01-02": 0}
    assert fake_session.get.call_count == 1
    assert fake_session.post.call_count == 1
    assert fake_session.post.call_args.kwargs["headers"]["Authorization"] == "token test-token"
    for call in [fake_session.post.call_args]:
        assert call.kwargs["headers"]["Authorization"] == "token test-token"


@patch("app.platforms.fetchers._get_http_session")
def test_fetch_github_rate_limited_403(mock_session_factory):
    rate_limited = make_response(status_code=403)
    rate_limited.json.side_effect = AssertionError("json() must not be called on 403")
    set_session_responses(mock_session_factory, [
        make_response(text="2 contributions on 2024-01-01"),
    ], [
        rate_limited,
    ])

    result = fetch_github("octocat")

    assert result["error"] == "rate_limited"
    assert result["stats"] is None
    assert result["calendar"] == {"2024-01-01": 2}


@patch("app.platforms.fetchers._get_http_session")
def test_fetch_github_rate_limited_429(mock_session_factory):
    rate_limited = make_response(status_code=429)
    rate_limited.json.side_effect = AssertionError("json() must not be called on 429")
    set_session_responses(mock_session_factory, [
        make_response(text="1 contributions on 2024-01-01"),
    ], [
        rate_limited,
    ])

    result = fetch_github("octocat")

    assert result["error"] == "rate_limited"
    assert result["stats"] is None
    assert result["calendar"] == {"2024-01-01": 1}


@patch("app.platforms.fetchers._get_http_session")
def test_fetch_github_no_token(mock_session_factory):
    fake_session = set_session_responses(mock_session_factory, [
        make_response(text="7 contributions on 2024-01-03"),
    ], [
        make_response(json_data={
            "data": {
                "issues": {"totalCount": 1},
                "prs": {"totalCount": 2},
                "mergedPrs": {"totalCount": 3},
                "commits": {"totalCount": 4},
            }
        }),
    ])

    env_without_token = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
    with patch.dict(os.environ, env_without_token, clear=True):
        result = fetch_github("octocat")

    assert "error" not in result
    assert result["stats"] == {"issues": 1, "prs": 2, "merged_prs": 3, "commits": 4}
    assert fake_session.get.call_count == 1
    assert fake_session.post.call_count == 1
    assert "Authorization" not in fake_session.post.call_args.kwargs.get("headers", {})
