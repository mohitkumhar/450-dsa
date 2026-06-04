# `get_merged_daily_counts` undercounts active days after `_legacy` migration completes

**Severity:** High
**Type:** Bug — Data Integrity / C-Score Regression
**Filed:** No

---

## Description

`get_merged_daily_counts()` is the authoritative function for computing a user's total daily submission activity. After the per-platform calendar migration completes (signalled by the removal of the `_legacy` key), overlapping dates between per-platform calendars and the original `external_daily_counts` field use the **per-platform value only**, discarding the (potentially higher) legacy cumulative count. This causes C-Score consistency scores to **decrease** for established users immediately after their first full post-migration sync.

## Root Cause

In `app/utils.py:236-268`:

```python
def get_merged_daily_counts(user_doc):
    platform_calendars = _get_field(user_doc, "platform_calendars", {})
    if isinstance(platform_calendars, dict) and platform_calendars:
        legacy_fallback = {}
        calendars = {}
        for key, value in platform_calendars.items():
            if key == "_legacy" and isinstance(value, dict):
                legacy_fallback = value          # ← _legacy data captured here
            else:
                calendars[key] = value           # ← per-platform calendars

        merged = {}
        for _platform, counts in calendars.items():       # Sum per-platform counts
            ...
            merged[date] = merged.get(date, 0) + count

        for date, count in legacy_fallback.items():        # Merge _legacy with MAX
            merged[date] = max(merged.get(date, 0), count)

        if merged:
            has_legacy_fallback = bool(legacy_fallback)
            legacy = _get_field(user_doc, "external_daily_counts", {})
            if isinstance(legacy, dict):
                for date, count in legacy.items():
                    if coerce_non_negative_number(count) > 0:
                        if has_legacy_fallback:
                            merged[date] = max(merged.get(date, 0), count)   # ← MAX when _legacy exists
                        elif date not in merged:                              # ← SKIP when _legacy absent!
                            merged[date] = count
            return merged
    return _get_field(user_doc, "external_daily_counts", {})
```

When `_legacy` **exists** (migration in progress), overlapping dates use `max()`. This correctly preserves the higher of the old and new values.

When `_legacy` is **absent** (migration complete, line 310 in `sync_service.py`), `has_legacy_fallback = False`, and the code falls to `elif date not in merged` — overlapping dates in `external_daily_counts` are **silently skipped**.

**The problem:** Per-platform API data is often **less complete** than the cumulative old data:

| Data Source | Coverage |
|-------------|----------|
| LeetCode GraphQL `submissionCalendar` | ~90 days of daily breakdown |
| Old `external_daily_counts` | Entire history (could be years) |

After the first full sync, `_legacy` is removed (because all configured platforms were synced). On the second call to `get_merged_daily_counts`, any date that exists in both the per-platform calendar and the old `external_daily_counts` will use ONLY the per-platform value — which may be lower because the API only returns recent data.

## Impact

- **C-Score consistency component decreases** — C-Score = `min(active_days / 365, 1.0) * 100`. If active days drop from 365 to 90, the consistency score drops from 100 to 24.
- **Profile "Total Active Days" decreases** — User sees a regression after syncing.
- **Heatmap shows fewer active days** — Days older than the API window disappear from the visualization.
- **Long-time users are most affected** — Users with >1 year of history lose the most.

## Sync Flow Interaction

In `app/profile/sync_service.py:308-310`:
```python
if user_platforms and requested_platforms and user_platforms.issubset(requested_platforms):
    platform_calendars.pop("_legacy", None)   # ← removes the safety net
```

This removal is correct in intent (migration is complete), but the downstream `get_merged_daily_counts` handler then permanently loses the old cumulative data for overlapping dates.

## Suggested Fix

Always use `max()` when merging `external_daily_counts`, regardless of `_legacy` presence:

```python
# Change lines 263-266 from:
if has_legacy_fallback:
    merged[date] = max(merged.get(date, 0), count)
elif date not in merged:
    merged[date] = count

# To:
merged[date] = max(merged.get(date, 0), count)
```

This ensures the old cumulative `external_daily_counts` data always serves as a **floor** for per-platform data, preventing regressions while still allowing per-platform calendards to contribute new data.

## Files Involved

- `app/utils.py:263-266` — The `elif date not in merged` guard that loses data
- `app/utils.py:236-268` — Full `get_merged_daily_counts()` function
- `app/profile/sync_service.py:308-310` — `_legacy` removal after full sync
- `app/profile/routes.py:387-390` — Profile route consumes merged counts for heatmap
- `app/utils.py:294-296` — `compute_c_score()` uses merged counts for consistency score
