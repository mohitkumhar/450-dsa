# Progress import replace mode silently deletes all unmatched question progress

**Severity:** Critical
**Type:** Bug — Data Loss
**Filed:** No

---

## Description

The progress import's "replace" mode (`mode=replace`) in `import_commit()` overwrites the user's entire `progress` document with only the items that were present in the uploaded backup file. Any existing question progress that is not matched by a record in the backup file is **permanently and silently deleted**.

## Root Cause

In `app/tracker/routes.py`, `import_commit()` at line 566-593:

```python
else:  # replace mode
    for q_id, imp_val in mapped_progress.items():
        existing = current_db_progress.get(q_id, {})
        timestamp = existing.get("timestamp")
        if imp_val["done"] and not existing.get("done"):
            timestamp = utc_now()
        elif not timestamp:
            timestamp = utc_now()

        new_progress[q_id] = {
            "done": imp_val["done"],
            "bookmark": imp_val["bookmark"],
            "skipped": imp_val["skipped"] if not imp_val["done"] else False,
            "notes": imp_val["notes"],
            "timestamp": timestamp
        }
```

`mapped_progress` only contains question IDs that **both** existed in the import file **and** were matched to a DB question. All existing progress entries NOT in this set are absent from `new_progress`. Then at line 586-594:

```python
db.user.update_one(
    {"_id": user_id},
    {"$set": {
        "progress": new_progress,
        "in_sheet_platform_counts": in_sheet_counts
    }}
)
```

The `$set` replaces the entire `progress` document, dropping every entry not in `new_progress`.

In contrast, "merge" mode (`mode=merge`) at line 536-565 correctly preserves existing entries:
```python
new_progress = dict(current_db_progress)  # Start with ALL existing progress
for q_id, imp_val in mapped_progress.items():
    existing = new_progress.get(q_id, {})
    # ... merge each imported entry
```

## Impact

A user who exports a progress CSV/JSON (containing, say, 20 questions), then re-imports that same file in replace mode will lose progress on every other question they had marked (e.g., the other 430+ questions). The operation is instant and irreversible — there is no undo.

## Steps to Reproduce

1. Mark 50 questions as done on the tracker
2. Export progress as JSON → this file contains all 50 entries
3. Delete 40 entries from the exported JSON file
4. Import the edited file using "Replace (Overwrite)" mode
5. Observe: only 10 questions remain marked. The other 40 are gone permanently.

## Suggested Fix

The replace mode should preserve entries not present in the import file, similar to merge mode:

```python
else:  # replace mode
    new_progress = {}
    # First, copy over existing entries that are NOT in the import
    for q_id, existing in current_db_progress.items():
        if q_id not in mapped_progress:
            new_progress[q_id] = dict(existing)
    # Then apply imported changes
    for q_id, imp_val in mapped_progress.items():
        ...
```

Alternatively, the dry-run preview (`import_preview`) should show a count of entries that **would be dropped** by replace mode and reject the import if this count is non-zero unless the user explicitly confirms.

## Files Involved

- `app/tracker/routes.py:566-594` — Replace mode builds `new_progress` from only `mapped_progress`
- `app/tracker/routes.py:536-565` — Merge mode (correct) for comparison
- `templates/profile.html:503-516` — UI radio button selects mode, but no warning shown
