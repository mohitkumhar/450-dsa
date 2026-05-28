import secrets
from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app, abort
from flask_login import current_user, login_required

from app.extensions import db
from app.utils import compute_c_score, utc_now

cohort_bp = Blueprint("cohort", __name__)


@cohort_bp.route("/cohorts")
@login_required
def index():
    # Find all membership records for this user
    memberships = list(db.cohort_membership.find({"user_id": current_user.id}))
    cohort_ids = [m["cohort_id"] for m in memberships]

    # Find cohort details and compute total member count for each
    cohorts = []
    if cohort_ids:
        cohort_docs = list(db.cohort.find({"_id": {"$in": cohort_ids}}))
        for cohort in cohort_docs:
            member_count = db.cohort_membership.count_documents({"cohort_id": cohort["_id"]})
            cohorts.append({
                "id": str(cohort["_id"]),
                "name": cohort.get("name"),
                "join_code": cohort.get("join_code"),
                "member_count": member_count,
            })

    return render_template("cohorts.html", cohorts=cohorts)


@cohort_bp.route("/cohorts/create", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Cohort name cannot be empty.", "danger")
        return redirect(url_for("cohort.index"))

    # Generate unique join code
    while True:
        join_code = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(6))
        if not db.cohort.find_one({"join_code": join_code}):
            break

    cohort_doc = {
        "name": name,
        "join_code": join_code,
        "created_by": current_user.id,
        "created_at": utc_now(),
    }
    result = db.cohort.insert_one(cohort_doc)
    cohort_id = result.inserted_id

    # Auto join creator
    db.cohort_membership.insert_one({
        "cohort_id": cohort_id,
        "user_id": current_user.id,
        "joined_at": utc_now()
    })

    flash(f"Cohort '{name}' created successfully! Share the code {join_code} with your friends.", "success")
    return redirect(url_for("cohort.detail", cohort_id=str(cohort_id)))


@cohort_bp.route("/cohorts/join", methods=["POST"])
@login_required
def join():
    join_code = request.form.get("join_code", "").strip().upper()
    if not join_code:
        flash("Please enter a join code.", "danger")
        return redirect(url_for("cohort.index"))

    cohort = db.cohort.find_one({"join_code": join_code})
    if not cohort:
        flash("Invalid join code. Please check the code and try again.", "danger")
        return redirect(url_for("cohort.index"))

    # Check membership
    existing = db.cohort_membership.find_one({
        "cohort_id": cohort["_id"],
        "user_id": current_user.id
    })
    if existing:
        flash("You are already a member of this cohort.", "warning")
        return redirect(url_for("cohort.detail", cohort_id=str(cohort["_id"])))

    db.cohort_membership.insert_one({
        "cohort_id": cohort["_id"],
        "user_id": current_user.id,
        "joined_at": utc_now()
    })

    flash(f"Successfully joined cohort '{cohort.get('name')}'!", "success")
    return redirect(url_for("cohort.detail", cohort_id=str(cohort["_id"])))


@cohort_bp.route("/cohorts/<cohort_id>")
@login_required
def detail(cohort_id):
    try:
        cohort_id_obj = ObjectId(cohort_id)
    except InvalidId:
        abort(404)

    cohort = db.cohort.find_one({"_id": cohort_id_obj})
    if not cohort:
        abort(404)

    # Check if current user is a member
    membership = db.cohort_membership.find_one({
        "cohort_id": cohort_id_obj,
        "user_id": current_user.id
    })
    if not membership:
        flash("You are not a member of this cohort.", "danger")
        return redirect(url_for("cohort.index"))

    # Get all memberships for the cohort
    memberships = list(db.cohort_membership.find({"cohort_id": cohort_id_obj}))
    user_ids = [m["user_id"] for m in memberships]

    # Query active users
    users = list(db.user.find(
        {"_id": {"$in": user_ids}, "is_deactivated": {"$ne": True}},
        {
            "name": 1,
            "email": 1,
            "profile_photo": 1,
            "college": 1,
            "leetcode_username": 1,
            "github_username": 1,
            "gfg_username": 1,
            "hackerrank_username": 1,
            "codingninjas_username": 1,
            "progress": 1,
            "external_totals": 1,
            "external_daily_counts": 1,
            "platform_calendars": 1,
        }
    ))

    # Compute leaderboards
    pre = current_app.config.get("_PRECOMPUTED")
    all_questions = pre["all_questions"] if pre else list(db.question.find({}, {"url": 1}))

    entries = []
    for user in users:
        name = user.get("name", "Anonymous")
        if not name or name.strip() == "":
            continue
        stats = compute_c_score(user, all_questions=all_questions)
        entries.append({
            "user_id": str(user["_id"]),
            "name": name,
            "profile_photo": user.get("profile_photo", ""),
            "college": user.get("college", ""),
            "leetcode_username": user.get("leetcode_username", ""),
            "codingninjas_username": user.get("codingninjas_username", ""),
            **stats,
        })

    # Sort entries by c_score descending
    entries.sort(key=lambda item: item["c_score"], reverse=True)

    # Assign ranks
    for index, entry in enumerate(entries):
        entry["rank"] = index + 1

    return render_template(
        "cohort_detail.html",
        cohort=cohort,
        entries=entries,
        current_user_id=str(current_user.id)
    )
