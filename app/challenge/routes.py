from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, abort, render_template
from flask_login import current_user

from app.extensions import db
from app.utils import question_editorial_links

challenge_bp = Blueprint("challenge", __name__, url_prefix="/challenges")


def build_challenge_leaderboard(challenge_question_ids):
    challenge_question_id_strs = [str(qid) for qid in challenge_question_ids]

    users = list(
        db.user.find(
            {"is_deactivated": {"$ne": True}},
            {
                "name": 1,
                "email": 1,
                "profile_photo": 1,
                "progress": 1,
            },
        )
    )

    leaderboard = []
    for user in users:
        name = user.get("name") or user.get("email") or "Anonymous"
        if not name or name.strip() == "":
            continue

        progress = user.get("progress") or {}
        solved_count = 0
        latest_timestamp = None

        for qid_str in challenge_question_id_strs:
            prog_item = progress.get(qid_str)
            if prog_item and prog_item.get("done"):
                solved_count += 1
                ts = prog_item.get("timestamp")
                if ts:
                    # Parse timestamp if it is a string
                    if isinstance(ts, str):
                        try:
                            # Try parsing ISO format
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except ValueError:
                            ts = None
                    if ts:
                        if latest_timestamp is None or ts > latest_timestamp:
                            latest_timestamp = ts

        if solved_count > 0:
            leaderboard.append(
                {
                    "user_id": str(user["_id"]),
                    "name": name,
                    "profile_photo": user.get("profile_photo", ""),
                    "solved_count": solved_count,
                    "latest_timestamp": latest_timestamp,
                }
            )

    def sort_key(entry):
        ts = entry["latest_timestamp"]
        if ts is None:
            ts_val = datetime.max.replace(tzinfo=timezone.utc).timestamp()
        else:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_val = ts.timestamp()
        return (-entry["solved_count"], ts_val)

    leaderboard.sort(key=sort_key)
    for index, entry in enumerate(leaderboard):
        entry["rank"] = index + 1
    return leaderboard


@challenge_bp.route("")
def challenges():
    challenges_list = list(db.challenge.find().sort("week_num", 1))
    current_time = datetime.now(timezone.utc)

    # Determine active/current challenge
    current_challenge = None
    for ch in challenges_list:
        start = ch.get("start_date")
        end = ch.get("end_date")
        if start and end:
            # Ensure they are offset-aware
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if start <= current_time <= end:
                current_challenge = ch
                break

    # If no challenge matches by date, default to the latest week_num challenge
    if not current_challenge and challenges_list:
        current_challenge = challenges_list[-1]

    # Compute progress details for each challenge
    progress_dict = current_user.progress if current_user.is_authenticated else {}

    for ch in challenges_list:
        q_ids = [str(qid) for qid in ch.get("question_ids", [])]
        completed = sum(1 for qid in q_ids if progress_dict.get(qid, {}).get("done"))
        ch["total_questions"] = len(q_ids)
        ch["completed_questions"] = completed
        ch["progress_percent"] = int((completed / len(q_ids)) * 100) if q_ids else 0

    # Highlighted stats for current challenge
    current_leaderboard = []
    if current_challenge:
        current_leaderboard = build_challenge_leaderboard(
            current_challenge.get("question_ids", [])
        )[:5]

    return render_template(
        "challenge/list.html",
        challenges=challenges_list,
        current_challenge=current_challenge,
        current_leaderboard=current_leaderboard,
    )


@challenge_bp.route("/<challenge_id>")
def challenge_detail(challenge_id):
    try:
        challenge_id_obj = ObjectId(challenge_id)
    except InvalidId:
        abort(404)

    ch = db.challenge.find_one({"_id": challenge_id_obj})
    if not ch:
        abort(404)

    q_ids = ch.get("question_ids", [])
    questions = list(db.question.find({"_id": {"$in": q_ids}}))

    # Sort questions to maintain challenge defined order
    q_id_map = {str(qid): idx for idx, qid in enumerate(q_ids)}
    questions.sort(key=lambda q: q_id_map.get(str(q["_id"]), 999))

    # Add topic name to each question
    topic_ids = list({q["topic"] for q in questions if "topic" in q})
    topic_docs = {
        topic["_id"]: topic["name"]
        for topic in db.topic.find({"_id": {"$in": topic_ids}}, {"name": 1})
    }
    for q in questions:
        q["topic_name"] = topic_docs.get(q["topic"], "Unknown")
        q["editorial_links"] = question_editorial_links(q)

    # Compute user stats for the challenge
    progress_dict = current_user.progress if current_user.is_authenticated else {}
    completed_count = sum(
        1 for q in questions if progress_dict.get(str(q["_id"]), {}).get("done")
    )
    total_count = len(questions)
    progress_percent = int((completed_count / total_count) * 100) if total_count else 0

    # Get challenge leaderboard
    leaderboard = build_challenge_leaderboard(q_ids)

    return render_template(
        "challenge/detail.html",
        challenge=ch,
        questions=questions,
        progress_dict=progress_dict,
        completed_count=completed_count,
        total_count=total_count,
        progress_percent=progress_percent,
        leaderboard=leaderboard,
    )
