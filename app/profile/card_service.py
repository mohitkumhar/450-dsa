import time
from io import BytesIO

from bson.objectid import ObjectId

import card_generator

from app.extensions import db
from app.utils import compute_c_score, compute_user_platforms
from streaks import compute_streak


card_cache = {}
CACHE_TTL = 3600


def get_public_card_image(user_id, object_id=None, db_handle=None):
    current_time = time.time()
    if user_id in card_cache:
        cached_time, cached_image = card_cache[user_id]
        if current_time - cached_time < CACHE_TTL:
            cached_image.seek(0)
            return cached_image

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

    img_io = card_generator.generate_progress_card(
        name, c_score, dsa_progress, current_streak, platforms
    )
    if isinstance(img_io, BytesIO):
        img_io.seek(0)

    card_cache[user_id] = (current_time, img_io)
    return img_io
