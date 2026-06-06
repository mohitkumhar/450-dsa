import csv
import json
from io import StringIO
from datetime import datetime


def normalize_url(url):
    if not url:
        return ""
    url = url.strip().lower()
    if url.startswith("https://"):
        url = url[8:]
    elif url.startswith("http://"):
        url = url[7:]
    if url.startswith("www."):
        url = url[4:]
    if url.endswith("/"):
        url = url[:-1]
    return url


def parse_csv_backup(content_str):
    f = StringIO(content_str)
    reader = csv.reader(f)
    try:
        headers = next(reader)
    except StopIteration:
        return [], "Empty CSV file"

    header_map = {}
    for idx, h in enumerate(headers):
        header_map[h.strip().lower()] = idx

    if "problem" not in header_map:
        return [], "Invalid CSV format: 'Problem' column is required."

    parsed_items = []
    for row in reader:
        if not row:
            continue
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))

        def get_val(name, default=""):
            idx = header_map.get(name.lower())
            if idx is not None and idx < len(row):
                return row[idx]
            return default

        problem = get_val("Problem")
        if not problem:
            continue

        def parse_bool(val):
            val = str(val).strip().lower()
            return val in ("true", "1", "yes", "y", "done", "t")

        done = parse_bool(get_val("Done"))
        bookmark = parse_bool(get_val("Bookmarked")) or parse_bool(get_val("Bookmark"))
        skipped = parse_bool(get_val("Skipped"))

        notes = get_val("Notes")
        if notes.startswith("'") and len(notes) > 1 and notes[1] in ('=', '+', '-', '@'):
            notes = notes[1:]

        url = get_val("URL")
        url2 = get_val("URL2")

        revision_status = get_val("Revision Status") or get_val("revision_status")
        last_reviewed = get_val("Last Reviewed") or get_val("last_reviewed")

        parsed_items.append({
            "problem": problem,
            "url": url,
            "url2": url2,
            "done": done,
            "bookmark": bookmark,
            "skipped": skipped,
            "notes": notes,
            "revision_status": revision_status,
            "last_reviewed": last_reviewed,
        })

    return parsed_items, None


def parse_json_backup(content_str):
    try:
        data = json.loads(content_str)
    except Exception as e:
        return [], f"Invalid JSON syntax: {str(e)}"

    parsed_items = []
    if isinstance(data, list):
        items_list = data
    elif isinstance(data, dict) and "progress" in data:
        prog = data["progress"]
        if isinstance(prog, list):
            items_list = prog
        elif isinstance(prog, dict):
            items_list = []
            for key, val in prog.items():
                if isinstance(val, dict):
                    item = dict(val)
                    item["key"] = key
                    items_list.append(item)
        else:
            return [], "Invalid 'progress' format in JSON."
    elif isinstance(data, dict):
        items_list = []
        for key, val in data.items():
            if isinstance(val, dict):
                item = dict(val)
                item["key"] = key
                items_list.append(item)
    else:
        return [], "Invalid JSON structure."

    for item in items_list:
        if not isinstance(item, dict):
            continue

        def parse_bool(val):
            if isinstance(val, bool):
                return val
            val_str = str(val).strip().lower()
            return val_str in ("true", "1", "yes", "y", "done", "t")

        done = parse_bool(item.get("done") or item.get("Done"))
        bookmark = parse_bool(
            item.get("bookmark") or item.get("Bookmark") or item.get("bookmarked") or item.get("Bookmarked")
        )
        skipped = parse_bool(item.get("skipped") or item.get("Skipped"))
        notes = str(item.get("notes") or item.get("Notes") or "")

        problem = str(item.get("problem") or item.get("Problem") or "")
        url = str(item.get("url") or item.get("URL") or "")
        url2 = str(item.get("url2") or item.get("URL2") or "")
        key = str(item.get("key") or item.get("id") or item.get("_id") or "")

        revision_status = (
            item.get("revision_status")
            or item.get("Revision Status")
        )

        last_reviewed = (
            item.get("last_reviewed")
            or item.get("Last Reviewed")
        )

        if not problem and not url and not key:
            continue

        parsed_items.append({
            "problem": problem,
            "url": url,
            "url2": url2,
            "key": key,
            "done": done,
            "bookmark": bookmark,
            "skipped": skipped,
            "notes": notes,
            "revision_status" : revision_status,
            "last_reviewed" : last_reviewed,
        })

    return parsed_items, None


def process_dry_run(parsed_items, db_questions, current_progress):
    by_id = {}
    by_url = {}
    by_name = {}

    for q in db_questions:
        q_id = str(q["_id"])
        by_id[q_id] = q

        u1 = normalize_url(q.get("url"))
        if u1:
            by_url[u1] = q
        u2 = normalize_url(q.get("url2"))
        if u2:
            by_url[u2] = q

        name = q.get("problem", "").strip().lower()
        if name:
            by_name[name] = q

    matched_count = 0
    unmatched_count = 0
    changes = []
    conflicts = []
    mapped_progress = {}

    for item in parsed_items:
        target_question = None

        key = item.get("key")
        if key and key in by_id:
            target_question = by_id[key]

        if not target_question:
            u = normalize_url(item.get("url"))
            if u and u in by_url:
                target_question = by_url[u]

        if not target_question:
            u2 = normalize_url(item.get("url2"))
            if u2 and u2 in by_url:
                target_question = by_url[u2]

        if not target_question:
            name = item.get("problem", "").strip().lower()
            if name and name in by_name:
                target_question = by_name[name]

        if not target_question:
            unmatched_count += 1
            continue

        matched_count += 1
        q_id = str(target_question["_id"])
        problem_title = target_question["problem"]

        last_reviewed = item.get("last_reviewed")
        parsed_last_reviewed = None

        if last_reviewed:
            try:
                parsed_last_reviewed = datetime.fromisoformat(last_reviewed)
            except ValueError:
                parsed_last_reviewed = None

        mapped_progress[q_id] = {
            "done": item["done"],
            "bookmark": item["bookmark"],
            "skipped": item["skipped"],
            "notes": item["notes"],
            "revision_status": item.get(
                "revision_status",
            ),
           "last_reviewed": parsed_last_reviewed,
        }
        existing = current_progress.get(q_id, {})
        change_desc = []
        if item["done"] != bool(existing.get("done")):
            change_desc.append(f"Done: {existing.get('done', False)} -> {item['done']}")

        if item["bookmark"] != bool(existing.get("bookmark")):
            change_desc.append(f"Bookmark: {existing.get('bookmark', False)} -> {item['bookmark']}")

        if item["skipped"] != bool(existing.get("skipped")):
            change_desc.append(f"Skipped: {existing.get('skipped', False)} -> {item['skipped']}")

        db_notes = existing.get("notes") or ""
        imp_notes = item["notes"]
        if db_notes != imp_notes:
            change_desc.append("Notes updated")
            if db_notes and imp_notes:
                conflicts.append({
                    "problem": problem_title,
                    "field": "notes",
                    "db_value": db_notes,
                    "import_value": imp_notes,
                })

        if change_desc:
            changes.append({
                "problem": problem_title,
                "change": ", ".join(change_desc),
            })

    summary = {
        "total_records": len(parsed_items),
        "matched_records": matched_count,
        "unmatched_records": unmatched_count,
        "changes_detected": len(changes),
        "conflicts_detected": len(conflicts),
    }

    return summary, changes, conflicts, mapped_progress
