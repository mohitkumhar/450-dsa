from datetime import date, datetime, timezone

from streaks import compute_streak


def solved_on(timestamp):
    return {'done': True, 'timestamp': timestamp}


def test_compute_streak_counts_current_run_through_today():
    progress = {
        'a': solved_on(datetime(2026, 5, 18, tzinfo=timezone.utc)),
        'b': solved_on(datetime(2026, 5, 19, tzinfo=timezone.utc)),
        'c': solved_on(datetime(2026, 5, 20, tzinfo=timezone.utc)),
    }

    assert compute_streak(progress, today=date(2026, 5, 20)) == (3, 3)


def test_compute_streak_allows_yesterday_as_active_streak():
    progress = {
        'a': solved_on(datetime(2026, 5, 18, tzinfo=timezone.utc)),
        'b': solved_on(datetime(2026, 5, 19, tzinfo=timezone.utc)),
    }

    assert compute_streak(progress, today=date(2026, 5, 20)) == (2, 2)


def test_compute_streak_resets_current_when_gap_exceeds_yesterday():
    progress = {
        'a': solved_on(datetime(2026, 5, 15, tzinfo=timezone.utc)),
        'b': solved_on(datetime(2026, 5, 16, tzinfo=timezone.utc)),
        'c': solved_on(datetime(2026, 5, 18, tzinfo=timezone.utc)),
    }

    assert compute_streak(progress, today=date(2026, 5, 20)) == (0, 2)


def test_compute_streak_ignores_unsolved_or_missing_timestamps():
    progress = {
        'a': {'done': False, 'timestamp': datetime(2026, 5, 20, tzinfo=timezone.utc)},
        'b': {'done': True},
    }

    assert compute_streak(progress, today=date(2026, 5, 20)) == (0, 0)


def test_compute_streak_treats_naive_datetimes_as_utc():
    progress = {'a': solved_on(datetime(2026, 5, 20))}

    assert compute_streak(progress, today=date(2026, 5, 20)) == (1, 1)


def test_compute_streak_filters_zero_invalid_external_counts():
    progress = {
        'a': solved_on(datetime(2026, 5, 18, tzinfo=timezone.utc)),
        'b': solved_on(datetime(2026, 5, 19, tzinfo=timezone.utc)),
    }
    external_counts = {
        "2026-05-20": 3,
        "2026-05-21": 0,
        "2026-05-22": -1,
        "bad-date": 5,
        "2026-05-23": None,
    }

    current, longest = compute_streak(
        progress, today=date(2026, 5, 20), external_daily_counts=external_counts
    )
    assert current == 3
    assert longest == 3
