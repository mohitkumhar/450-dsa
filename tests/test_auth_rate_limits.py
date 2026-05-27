import app.auth.routes as auth_routes


def _route_limits(endpoint):
    decorated_limits = auth_routes.limiter.limit_manager._decorated_limits
    matching_key = f"app.auth.routes.{endpoint}.{endpoint}"
    return list(decorated_limits[matching_key])


def test_login_route_has_post_rate_limit():
    limit = _route_limits("login")[0]

    assert limit.limit_provider == "5 per minute"
    assert limit.methods == ("POST",)


def test_register_route_has_post_rate_limit():
    limit = _route_limits("register")[0]

    assert limit.limit_provider == "3 per hour"
    assert limit.methods == ("POST",)
