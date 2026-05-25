import re

import requests


REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
DEFAULT_REPO_LIMIT = 3
MAX_REPO_LIMIT = 6


def normalize_repo_list(raw_value, github_username, max_repos=MAX_REPO_LIMIT):
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raise ValueError("github_repo_list must be text")

    github_username = (github_username or "").strip()
    entries = []
    seen = set()

    for token in re.split(r"[\n,]+", raw_value):
        token = token.strip()
        if not token:
            continue

        slug = token
        if "/" not in slug:
            if not github_username:
                raise ValueError("GitHub repository names must include an owner when no GitHub username is set.")
            slug = f"{github_username}/{slug}"

        if not REPO_SLUG_RE.fullmatch(slug):
            raise ValueError("GitHub repositories must use owner/repo format with valid characters.")

        slug_key = slug.lower()
        if slug_key in seen:
            continue

        seen.add(slug_key)
        entries.append(slug)

        if len(entries) >= max_repos:
            break

    return "\n".join(entries)


def parse_repo_list(raw_value):
    if not raw_value:
        return []
    return [line.strip() for line in str(raw_value).splitlines() if line.strip()]


def fetch_repo_metadata(repo_slug, requests_module=requests):
    response = requests_module.get(
        f"https://api.github.com/repos/{repo_slug}",
        headers={"Accept": "application/vnd.github+json"},
        timeout=5,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    if payload.get("fork") or payload.get("private"):
        return None

    owner = payload.get("owner") or {}
    return {
        "slug": payload.get("full_name", repo_slug),
        "name": payload.get("name", repo_slug.split("/")[-1]),
        "url": payload.get("html_url"),
        "description": payload.get("description") or "",
        "language": payload.get("language") or "",
        "stars": payload.get("stargazers_count", 0),
        "forks": payload.get("forks_count", 0),
        "owner": owner.get("login", repo_slug.split("/")[0]),
    }


def fetch_github_repo_showcase(github_username, github_repo_list="", requests_module=requests):
    github_username = (github_username or "").strip()
    selected_repos = parse_repo_list(github_repo_list)

    if not github_username and not selected_repos:
        return []

    if selected_repos:
        showcase = []
        for repo_slug in selected_repos[:MAX_REPO_LIMIT]:
            metadata = fetch_repo_metadata(repo_slug, requests_module=requests_module)
            if metadata:
                showcase.append(metadata)
        return showcase

    response = requests_module.get(
        f"https://api.github.com/users/{github_username}/repos",
        params={"sort": "updated", "per_page": DEFAULT_REPO_LIMIT, "type": "owner"},
        headers={"Accept": "application/vnd.github+json"},
        timeout=5,
    )
    if response.status_code != 200:
        return []

    showcase = []
    for payload in response.json():
        if payload.get("fork") or payload.get("private"):
            continue
        showcase.append(
            {
                "slug": payload.get("full_name", ""),
                "name": payload.get("name", ""),
                "url": payload.get("html_url"),
                "description": payload.get("description") or "",
                "language": payload.get("language") or "",
                "stars": payload.get("stargazers_count", 0),
                "forks": payload.get("forks_count", 0),
                "owner": github_username,
            }
        )
        if len(showcase) >= DEFAULT_REPO_LIMIT:
            break

    return showcase
