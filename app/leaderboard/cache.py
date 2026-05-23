from flask import request

from app.extensions import cache


LEADERBOARD_CACHE_TIMEOUT = 300
LEADERBOARD_CACHE_VERSION_KEY = "leaderboard:cache-version"


def _leaderboard_cache_version():
    return cache.get(LEADERBOARD_CACHE_VERSION_KEY) or 0


def invalidate_leaderboard_cache():
    cache.set(LEADERBOARD_CACHE_VERSION_KEY, _leaderboard_cache_version() + 1)


def leaderboard_page_cache_key():
    return f"leaderboard:v{_leaderboard_cache_version()}:page:{request.path}"


def api_leaderboard_cache_key():
    args = tuple(sorted(request.args.items(multi=True)))
    return f"leaderboard:v{_leaderboard_cache_version()}:api:{request.path}:{args}"
