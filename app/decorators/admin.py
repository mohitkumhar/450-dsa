import time as _time
from functools import wraps

from flask import abort, current_app, session
from flask_login import current_user


def admin_required(view):
    """Allow access only for authenticated admin users.

    Checks session freshness on every admin request.  If the session has
    exceeded ADMIN_SESSION_TIMEOUT seconds since the last verified admin
    activity, the session is cleared and the request is rejected with 403.
    """

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if not bool(getattr(current_user, "is_admin", False)):
            abort(403)

        last_active = session.get("_admin_last_active")
        timeout = current_app.config.get("ADMIN_SESSION_TIMEOUT", 28800)
        if not last_active or _time.time() - last_active > timeout:
            session.clear()
            abort(403)

        session["_admin_last_active"] = _time.time()
        return view(*args, **kwargs)

    return wrapped_view