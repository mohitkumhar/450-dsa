import csv
import io
import json

from bson import ObjectId
from flask import current_app

from app.extensions import db
from app.utils import question_editorial_links

VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}


def _parse_json(raw):
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of topic objects")
    for topic in data:
        if not isinstance(topic, dict):
            raise ValueError(f"Expected a topic object, got {type(topic).__name__}")
        if "topicName" not in topic or "questions" not in topic:
            raise ValueError(f"Topic object missing 'topicName' or 'questions': {topic.get('topicName', '?')}")
        if not isinstance(topic["questions"], list):
            raise ValueError(f"Topic '{topic['topicName']}' questions must be a list")
    return data


def _parse_csv(raw):
    reader = csv.DictReader(io.StringIO(raw))
    topics_map = {}
    for row in reader:
        topic_name = (row.get("Topic") or "").strip()
        if not topic_name:
            continue
        if topic_name not in topics_map:
            topics_map[topic_name] = {
                "topicName": topic_name,
                "position": _int_or(row.get("Position"), 0),
                "questions": [],
            }
        topics_map[topic_name]["questions"].append({
            "Problem": (row.get("Problem") or "").strip(),
            "URL": (row.get("URL") or "").strip(),
            "URL2": (row.get("URL2") or "").strip(),
            "difficulty": (row.get("Difficulty") or "Medium").strip(),
        })
    if not topics_map:
        raise ValueError("CSV must have at least one row with a Topic column")
    return list(topics_map.values())


def _int_or(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_import_data(content, filename):
    if filename.lower().endswith(".csv"):
        return _parse_csv(content)
    return _parse_json(content)


def validate_import_data(parsed):
    errors = []
    seen_topics = {}
    for ti, topic in enumerate(parsed):
        tname = topic.get("topicName", "").strip()
        if not tname:
            errors.append(f"Topic #{ti + 1}: missing 'topicName'")
            continue
        key = tname.lower()
        if key in seen_topics:
            errors.append(f"Duplicate topic: '{tname}' (same as #{seen_topics[key] + 1})")
        seen_topics[key] = ti

        position = _int_or(topic.get("position"), 0)
        if position < 0:
            errors.append(f"Topic '{tname}': position must be non-negative")

        seen_questions = {}
        for qi, question in enumerate(topic.get("questions", [])):
            problem = (question.get("Problem") or "").strip()
            url = (question.get("URL") or "").strip()
            if not problem:
                errors.append(f"Topic '{tname}', question #{qi + 1}: missing 'Problem'")
            if not url:
                errors.append(f"Topic '{tname}', question #{qi + 1}: missing 'URL'")
            diff = question.get("difficulty", "Medium")
            if diff not in VALID_DIFFICULTIES:
                errors.append(f"Topic '{tname}', '{problem}': invalid difficulty '{diff}' (must be Easy/Medium/Hard)")

            qkey = f"{problem.lower()}|{url.lower()}"
            if qkey in seen_questions:
                errors.append(f"Topic '{tname}': duplicate question '{problem}' ({url})")
            seen_questions[qkey] = qi

    return errors


def preview_import(parsed):
    new_topics = 0
    existing_topics = 0
    new_questions = 0
    existing_questions = 0
    updated_questions = 0

    for topic in parsed:
        tname = topic["topicName"].strip()
        existing_topic = db.topic.find_one({"name": tname}, {"_id": 1})
        if existing_topic:
            existing_topics += 1
            topic_id = existing_topic["_id"]
        else:
            new_topics += 1
            topic_id = None

        for question in topic.get("questions", []):
            problem = (question.get("Problem") or "").strip()
            url = (question.get("URL") or "").strip()
            if not problem or not url:
                continue

            if topic_id:
                existing_q = db.question.find_one(
                    {"topic": topic_id, "problem": problem, "url": url},
                    {"_id": 1, "difficulty": 1},
                )
                if existing_q:
                    if existing_q.get("difficulty") != question.get("difficulty", "Medium"):
                        updated_questions += 1
                    else:
                        existing_questions += 1
                else:
                    new_questions += 1
            else:
                new_questions += 1

    return {
        "new_topics": new_topics,
        "existing_topics": existing_topics,
        "new_questions": new_questions,
        "existing_questions": existing_questions,
        "updated_questions": updated_questions,
    }


def apply_import(parsed):
    upserted_topic_ids = set()

    for topic in parsed:
        tname = topic["topicName"].strip()
        position = _int_or(topic.get("position"), 0)

        db.topic.update_one(
            {"name": tname},
            {"$set": {"position": position}},
            upsert=True,
        )
        topic_doc = db.topic.find_one({"name": tname})
        if not topic_doc:
            continue
        topic_id = topic_doc["_id"]
        upserted_topic_ids.add(str(topic_id))

        for question in topic.get("questions", []):
            problem = (question.get("Problem") or "").strip()
            url = (question.get("URL") or "").strip()
            if not problem or not url:
                continue

            difficulty = question.get("difficulty", "Medium")
            set_fields = {
                "url2": question.get("URL2", ""),
                "editorial_links": question_editorial_links(question),
                "difficulty": difficulty,
            }
            if "hints" in question:
                set_fields["hints"] = question["hints"]

            db.question.update_one(
                {"topic": topic_id, "problem": problem, "url": url},
                {"$set": set_fields},
                upsert=True,
            )

    config = current_app.config
    if "_PRECOMPUTED" in config:
        del config["_PRECOMPUTED"]
