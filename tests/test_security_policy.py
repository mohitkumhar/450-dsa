from app.security import DEFAULT_CSP_DIRECTIVES, build_content_security_policy


def test_build_content_security_policy_uses_default_directives():
    policy = build_content_security_policy()

    assert policy.endswith(";")
    assert "default-src 'self';" in policy
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com;" in policy
    assert "https://code.jquery.com" not in policy


def test_build_content_security_policy_accepts_custom_directives():
    policy = build_content_security_policy(
        {
            "default-src": ["'self'"],
            "connect-src": ["'self'", "https://api.example.com"],
        }
    )

    assert policy == "default-src 'self'; connect-src 'self' https://api.example.com;"


def test_default_csp_directives_keep_expected_origins():
    assert DEFAULT_CSP_DIRECTIVES["style-src"] == [
        "'self'",
        "'unsafe-inline'",
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",
    ]
    assert DEFAULT_CSP_DIRECTIVES["font-src"] == [
        "'self'",
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",
    ]
