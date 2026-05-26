import hashlib
import json
from datetime import timezone
from io import BytesIO

from bson.objectid import ObjectId

import card_generator

from app.extensions import cache, db
from app.utils import compute_c_score, compute_user_platforms, ensure_utc_datetime
from streaks import compute_streak


CACHE_TTL = 3600


def _build_card_etag(name, c_score, dsa_progress, current_streak, platforms):
    payload = {
        "name": name,
        "c_score": c_score,
        "dsa_progress": dsa_progress,
        "current_streak": current_streak,
        "platforms": platforms,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"progress-card-{digest}"


def _card_last_modified(user, progress_data):
    candidates = []

    updated_at = ensure_utc_datetime(user.get("updated_at"))
    if updated_at:
        candidates.append(updated_at)

    for progress_item in progress_data.values():
        solved_at = ensure_utc_datetime(progress_item.get("timestamp"))
        if solved_at and progress_item.get("done"):
            candidates.append(solved_at)

    if candidates:
        return max(candidates)

    object_id = user.get("_id")
    if isinstance(object_id, ObjectId):
        return object_id.generation_time.astimezone(timezone.utc)

    return None


def get_public_card_image(user_id, object_id=None, db_handle=None):
    db_handle = db_handle or db
    object_id = object_id or ObjectId(user_id)
    user = db_handle.user.find_one({"_id": object_id})
    if not user:
        raise LookupError("User not found")

    name = user.get("name", "Anonymous")

    stats = compute_c_score(user)
    c_score = stats["c_score"]
    dsa_done = stats["dsa_done"]

    total_questions = db_handle.question.count_documents({})
    dsa_progress = round((dsa_done / total_questions * 100) if total_questions > 0 else 0, 1)

    progress_data = user.get("progress", {})
    current_streak, _ = compute_streak(progress_data)

    all_questions = list(db_handle.question.find())
    solved_items = {qid: progress for qid, progress in progress_data.items() if progress.get("done")}
    platforms = compute_user_platforms(solved_items, user.get("external_totals", {}), all_questions)
    etag = _build_card_etag(name, c_score, dsa_progress, current_streak, platforms)
    last_modified = _card_last_modified(user, progress_data)

    cached = cache.get(f"card_{user_id}")
    if cached is not None:
        cached_etag, cached_bytes = cached
        if cached_etag == etag:
            return BytesIO(cached_bytes), etag, last_modified

    img_io = card_generator.generate_progress_card(
        name, c_score, dsa_progress, current_streak, platforms
    )
    if isinstance(img_io, BytesIO):
        img_io.seek(0)

    cache.set(f"card_{user_id}", (etag, img_io.getvalue()), timeout=CACHE_TTL)
    return img_io, etag, last_modified
