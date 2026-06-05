# Account deletion and deactivation leave stale data in leaderboard and card caches

**Severity:** High
**Type:** Bug — Data Privacy / Cache Staleness
**Filed:** No

---

## Description

When a user deletes or deactivates their account (or an admin deletes a user), the user document is removed or flagged from MongoDB, but **no cache invalidation** is performed. The in-memory leaderboard cache (TTL: 300s) continues to serve the deleted/deactivated user's C-Score, total solved, and ranking. The public progress card cache (TTL: 3600s) still stores the user's card image. For irreversible account deletion, this means deleted user data remains publicly accessible for up to **1 hour**.

## Root Cause

**User self-delete** — `app/auth/routes.py:244-246`:
```python
user_id = current_user.id
logout_user()
db.user.delete_one({"_id": user_id})
flash("Your account has been permanently deleted.", "info")
return redirect(url_for("auth.login"))
```
No cache invalidation. Compare with `sync_user_platforms` at `sync_service.py:320-321` which correctly calls both:
```python
invalidate_leaderboard_cache()
clear_profile_caches(cache_backend, user_id)
```

**User deactivation** — `app/auth/routes.py:270-274`:
```python
db.user.update_one(
    {"_id": current_user.id},
    {"$set": {"is_deactivated": True, "deactivated_at": utc_now()}},
)
logout_user()
```
No cache invalidation.

**Admin user delete** — `app/admin/routes.py:197-200`:
```python
result = db.user.delete_one({"_id": target_id})
if result.deleted_count != 1:
    abort(500)
flash(f"Deleted account for {display_name}.", "success")
```
No cache invalidation.

## Impact

| Scenario | Problem | Duration |
|----------|---------|----------|
| User deletes account → user's data on leaderboard | Deleted user still ranked | Up to 5 min |
| User deletes account → user's public card served | Deleted user's progress image served to anyone with the URL | Up to 60 min |
| User deactivates account → expected immediate hide | User still visible on leaderboard | Up to 5 min |
| Admin deletes user | Same as self-delete | Up to 5 min |

For **irreversible account deletion**, this is a privacy concern: the user's data should be immediately inaccessible after deletion. The card endpoint at `/u/<user_id>/card.png` does check `find_one` before returning data, but if the card is **warm in cache**, `get_public_card_image` returns the cached bytes directly (line 82-86 of `card_service.py`), avoiding the `find_one` check that happens **after** the cache bypass:

Looking at `app/profile/routes.py:209-218`:
```python
user_doc = db.user.find_one({"_id": object_id}, {"is_deactivated": 1})
...
if not user_doc or user_doc.get("is_deactivated"):
    return "User not found", 404

img_io, etag, last_modified = get_public_card_image(user_id, object_id, db_handle=db)
```

The `find_one` check happens **before** the cache lookup inside `get_public_card_image`. So for fresh requests the deleted user gets 404. However, the cache entry `card_{user_id}` is never invalidated, wasting memory.

The leaderboard cache (`build_leaderboard_data`) stores computed entries as a list. Deleted users remain in this cached list until eviction.

## Suggested Fix

Add cache invalidation to all three deletion/deactivation paths:

**For `auth/routes.py` `delete_account()`:**
```python
from app.leaderboard.cache import invalidate_leaderboard_cache
from app.profile.sync_service import clear_profile_caches
from app.extensions import cache

user_id = current_user.id
logout_user()
db.user.delete_one({"_id": user_id})
invalidate_leaderboard_cache()
clear_profile_caches(cache, user_id)
cache.delete(f"card_{user_id}")
```

**For `auth/routes.py` `deactivate_account()`:**
Same invalidation calls.

**For `admin/routes.py` `delete_user()`:**
Add invalidation calls before or after the `delete_one`.

## Files Involved

- `app/auth/routes.py:244-246` — Self-delete missing cache invalidation
- `app/auth/routes.py:270-274` — Deactivation missing cache invalidation
- `app/admin/routes.py:197-200` — Admin delete missing cache invalidation
- `app/leaderboard/cache.py` — Contains `invalidate_leaderboard_cache()`
- `app/profile/sync_service.py:39-43` — Contains `clear_profile_caches()`
- `app/profile/card_service.py:82-86` — Card cache bypass path
