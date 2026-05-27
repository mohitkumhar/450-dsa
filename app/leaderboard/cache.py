from flask import request
from flask_login import current_user

from app.extensions import cache


LEADERBOARD_CACHE_TIMEOUT = 300
LEADERBOARD_CACHE_VERSION_KEY = "leaderboard:cache-version"


def _leaderboard_cache_version():
    try:
        return cache.get(LEADERBOARD_CACHE_VERSION_KEY) or 0
    except KeyError:
        return 0


def invalidate_leaderboard_cache():
    try:
        cache.set(LEADERBOARD_CACHE_VERSION_KEY, _leaderboard_cache_version() + 1)
    except KeyError:
        pass


def leaderboard_page_cache_key():
    user_key = f"user:{current_user.get_id()}" if current_user.is_authenticated else "anon"
    return f"leaderboard:v{_leaderboard_cache_version()}:page:{request.path}:{user_key}"


def api_leaderboard_cache_key():
    args = tuple(sorted(request.args.items(multi=True)))
    return f"leaderboard:v{_leaderboard_cache_version()}:api:{request.path}:{args}"
