from datetime import date, datetime, timedelta, timezone


def _to_utc_date(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    return None


def compute_streak(progress, today=None, external_daily_counts=None):
    today = today or datetime.now(timezone.utc).date()
    solved_dates = {
        solved_date
        for item in progress.values()
        if item.get('done')
        for solved_date in (_to_utc_date(item.get('timestamp')),)
        if solved_date
    }

    if external_daily_counts:
        for date_str, count in external_daily_counts.items():
            try:
                if count and int(count) > 0:
                    d = date.fromisoformat(date_str)
                    solved_dates.add(d)
            except (ValueError, TypeError):
                pass

    if not solved_dates:
        return 0, 0

    longest_streak = 0
    run_length = 0
    previous_date = None

    for solved_date in sorted(solved_dates):
        if previous_date and solved_date == previous_date + timedelta(days=1):
            run_length += 1
        else:
            run_length = 1

        longest_streak = max(longest_streak, run_length)
        previous_date = solved_date

    anchor_date = today if today in solved_dates else today - timedelta(days=1)
    current_streak = 0
    while anchor_date in solved_dates:
        current_streak += 1
        anchor_date -= timedelta(days=1)

    return current_streak, longest_streak
