import math
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask import session
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import cache, db
from app.leaderboard.cache import invalidate_leaderboard_cache
from app.profile.sync_service import clear_profile_caches
from app.utils import get_merged_daily_counts
from app.utils.helpers import log_admin_action

admin_bp = Blueprint("admin", __name__, template_folder="templates")

def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

@admin_bp.route("/dashboard", methods=["GET"])
@login_required
@admin_required
def dashboard():
    """Admin control panel interface metric layout render."""
    return render_template("admin/dashboard.html")

@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    search_term = (request.form.get("q") or request.args.get("q") or "").strip()
    page = max(_safe_int(request.form.get("page") or request.args.get("page"), 1), 1)

    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        abort(400)

    if not ObjectId.is_valid(user_id):
        flash("Invalid user id.", "danger")
        return redirect(url_for("admin.users", q=search_term, page=page))

    log_admin_action(
        action_type="DELETE_USER",
        target_entity="USER",
        target_id=user_id,
        result="SUCCESS"
    )

    db.users.delete_one({"_id": ObjectId(user_id)})
    clear_profile_caches(user_id)
    
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin.users", q=search_term, page=page))
