import secrets

from flask import request, session


CSRF_SESSION_KEY = "csrf_token"
DELETE_ACCOUNT_CSRF_SESSION_KEY = "delete_csrf_token"
DEACTIVATE_ACCOUNT_CSRF_SESSION_KEY = "deactivate_csrf_token"
CSRF_HEADER_NAMES = ("X-CSRFToken", "X-CSRF-Token")
CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

DEFAULT_CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net"],
    "font-src": ["'self'", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"],
    "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://unpkg.com"],
    "img-src": ["'self'", "data:", "https:"],
}


def build_content_security_policy(directives=None):
    policy_directives = directives or DEFAULT_CSP_DIRECTIVES
    return "; ".join(
        f"{directive} {' '.join(sources)}" for directive, sources in policy_directives.items()
    ) + ";"


def csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def _request_csrf_token():
    for header_name in CSRF_HEADER_NAMES:
        token = request.headers.get(header_name)
        if token:
            return token

    token = request.form.get("csrf_token")
    if token:
        return token

    data = request.get_json(silent=True) if request.is_json else None
    if isinstance(data, dict):
        return data.get("csrf_token") or data.get("_csrf_token")

    return None


def _matches_token(token, expected):
    return bool(token and expected and secrets.compare_digest(str(token), str(expected)))


def validate_csrf_request():
    token = _request_csrf_token()
    if _matches_token(token, session.get(CSRF_SESSION_KEY)):
        return True

    if request.endpoint == "auth.delete_account":
        return _matches_token(token, session.get(DELETE_ACCOUNT_CSRF_SESSION_KEY))

    if request.endpoint == "auth.deactivate_account":
        return _matches_token(token, session.get(DEACTIVATE_ACCOUNT_CSRF_SESSION_KEY))

    return False
