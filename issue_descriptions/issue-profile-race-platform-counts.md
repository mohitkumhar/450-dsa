# Race condition between profile page GET and question toggle POST corrupts platform submission counts

**Severity:** High
**Type:** Bug — Race Condition / Data Integrity
**Filed:** No

---

## Description

A GET request to `/profile` performs a MongoDB `$set` write on `in_sheet_platform_counts` when the field has not yet been cached on the user document. A concurrent `POST` to `/update_question/<id>` uses `$inc` to adjust the same field. If the `$inc` executes before the `$set`, the increment's effect is **silently overwritten**, causing platform submission counts to diverge from reality.

## Root Cause

**In `app/profile/routes.py` lines 406-408** (profile page GET handler):

```python
if user.in_sheet_platform_counts:
    platforms = merge_platform_counts(user.in_sheet_platform_counts, ext_platform_totals)
else:
    in_sheet_counts = compute_in_sheet_platform_counts(solved_items, all_questions)
    db.user.update_one({"_id": user.id}, {"$set": {"in_sheet_platform_counts": in_sheet_counts}})
    platforms = merge_platform_counts(in_sheet_counts, ext_platform_totals)
```

The `$set` replaces the **entire** `in_sheet_platform_counts` document.

**In `app/tracker/routes.py` lines 268-279** (question toggle POST handler):

```python
platform_count_field = f"in_sheet_platform_counts.{platform_from_question_url(question.get('url'))}"
...
update_fields[platform_count_field] = 1   # or -1
...
# Later converted to $inc:
inc_fields = {
    field: update_fields.pop(field)
    for field in list(update_fields)
    if field.startswith("in_sheet_platform_counts.")
}
...
db.user.update_one({"_id": user_id}, update_doc)  # Contains $inc
```

The `$inc` atomically increments/decrements a **single platform key**.

**The Race:**

```
Time ────────────────────────────────────────────────>
                                                         Result
Profile GET:  $set {LeetCode: 5, GFG: 3}                  ← 5, 3 (WRONG!)
Toggle POST:  $inc {LeetCode: +1}  (writes first,
               then profile GET $set overwrites)
```

The `$set` from the profile GET **replaces the entire** `in_sheet_platform_counts` object, destroying the atomically incremented count. The increment is lost with no error or warning.

The reverse order is fine:
```
Toggle POST:  $inc {LeetCode: +1}  (writes second, after $set)
Profile GET:  $set {LeetCode: 5, GFG: 3}                   ← 6, 3 (correct)
```

## Impact

- Platform counts (`LeetCode`, `GFG`, `Coding Ninjas`, etc.) silently drift wrong
- The error propagates to `merge_platform_counts()` → `global_total_solved` on the profile page
- The public progress card uses merged counts → wrong card
- C-Score uses `compute_total_solved()` which sums platform counts → wrong leaderboard ranking
- The error is transient and self-corrects on the next profile page load, making it hard to detect

## Trigger Scenarios

High probability in real usage:
1. User opens their profile page in one tab
2. User toggles a question as done/undone in another tab
3. Both requests happen within milliseconds of each other

## Suggested Fix

**Option A (preferred):** Remove the side-effect write from the GET handler entirely. Compute platform counts lazily only when needed and always from scratch using the authoritative `progress` field.

**Option B:** Use `$inc` instead of `$set` in the profile route to avoid overwrites. First read the existing document, compute the delta for each platform, and apply `$inc` for each:

```python
delta = compute_platform_delta(solved_items, all_questions, user.in_sheet_platform_counts)
if delta:
    db.user.update_one({"_id": user.id}, {"$inc": delta})
```

**Option C:** Move the `$set` into the response rendering phase with an atomic `$setOnInsert`-style guard using a version field.

## Files Involved

- `app/profile/routes.py:406-408` — Profile GET performs destructive `$set`
- `app/tracker/routes.py:268-279, 303-314` — Question toggle uses `$inc`
- `app/utils.py:355-374` — `merge_platform_counts()` consumes the corrupted field
