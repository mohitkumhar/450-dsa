from types import SimpleNamespace

import pytest

from app.github_showcase import (
    DEFAULT_REPO_LIMIT,
    fetch_github_repo_showcase,
    normalize_repo_list,
)


def test_normalize_repo_list_uses_github_username_for_bare_names():
    normalized = normalize_repo_list("repo-one\nrepo-two", "saurabhhhcodes")

    assert normalized == "saurabhhhcodes/repo-one\nsaurabhhhcodes/repo-two"


def test_normalize_repo_list_deduplicates_case_insensitively():
    normalized = normalize_repo_list(
        "OpenAI/Codex\nopenai/codex\nOpenAI/Agents",
        "ignored-user",
    )

    assert normalized == "OpenAI/Codex\nOpenAI/Agents"


def test_normalize_repo_list_rejects_invalid_repo_slug():
    with pytest.raises(ValueError, match="owner/repo format"):
        normalize_repo_list("bad slug!", "saurabhhhcodes")


def test_fetch_github_repo_showcase_uses_selected_repositories():
    responses = {
        "https://api.github.com/repos/saurabhhhcodes/repo-one": SimpleNamespace(
            status_code=200,
            json=lambda: {
                "full_name": "saurabhhhcodes/repo-one",
                "name": "repo-one",
                "html_url": "https://github.com/saurabhhhcodes/repo-one",
                "description": "First repo",
                "language": "Python",
                "stargazers_count": 10,
                "forks_count": 2,
                "owner": {"login": "saurabhhhcodes"},
                "fork": False,
                "private": False,
            },
        ),
        "https://api.github.com/repos/saurabhhhcodes/repo-two": SimpleNamespace(
            status_code=200,
            json=lambda: {
                "full_name": "saurabhhhcodes/repo-two",
                "name": "repo-two",
                "html_url": "https://github.com/saurabhhhcodes/repo-two",
                "description": "Second repo",
                "language": "JavaScript",
                "stargazers_count": 8,
                "forks_count": 1,
                "owner": {"login": "saurabhhhcodes"},
                "fork": False,
                "private": False,
            },
        ),
    }

    def fake_get(url, headers=None, timeout=None, params=None):
        return responses[url]

    fake_requests = SimpleNamespace(get=fake_get)

    showcase = fetch_github_repo_showcase(
        "saurabhhhcodes",
        "saurabhhhcodes/repo-one\nsaurabhhhcodes/repo-two",
        requests_module=fake_requests,
    )

    assert [repo["slug"] for repo in showcase] == [
        "saurabhhhcodes/repo-one",
        "saurabhhhcodes/repo-two",
    ]
    assert showcase[0]["stars"] == 10
    assert showcase[1]["language"] == "JavaScript"


def test_fetch_github_repo_showcase_falls_back_to_recent_owned_repositories():
    payload = [
        {
            "full_name": "saurabhhhcodes/active-repo",
            "name": "active-repo",
            "html_url": "https://github.com/saurabhhhcodes/active-repo",
            "description": "Fresh work",
            "language": "Python",
            "stargazers_count": 7,
            "forks_count": 0,
            "fork": False,
            "private": False,
        },
        {
            "full_name": "saurabhhhcodes/forked-repo",
            "name": "forked-repo",
            "html_url": "https://github.com/saurabhhhcodes/forked-repo",
            "description": "Should not show",
            "language": "Go",
            "stargazers_count": 99,
            "forks_count": 10,
            "fork": True,
            "private": False,
        },
    ]
    captured = {}

    def fake_get(url, headers=None, timeout=None, params=None):
        captured["url"] = url
        captured["params"] = params
        return SimpleNamespace(status_code=200, json=lambda: payload)

    fake_requests = SimpleNamespace(get=fake_get)

    showcase = fetch_github_repo_showcase("saurabhhhcodes", requests_module=fake_requests)

    assert captured["url"] == "https://api.github.com/users/saurabhhhcodes/repos"
    assert captured["params"] == {"sort": "updated", "per_page": DEFAULT_REPO_LIMIT, "type": "owner"}
    assert [repo["slug"] for repo in showcase] == ["saurabhhhcodes/active-repo"]
