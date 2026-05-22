from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(view):
    """Allow access only for authenticated admin users."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if not bool(getattr(current_user, "is_admin", False)):
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view