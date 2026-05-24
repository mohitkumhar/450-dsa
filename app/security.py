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
