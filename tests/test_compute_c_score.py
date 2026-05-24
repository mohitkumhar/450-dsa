from app.utils import compute_c_score, compute_total_solved


def make_user(progress=None, external_totals=None, external_daily_counts=None):
    """Helper to build a minimal user_doc."""
    return {
        "progress": progress or {},
        "external_totals": external_totals or {},
        "external_daily_counts": external_daily_counts or {},
    }


# --- Empty user ---

def test_empty_user_returns_zero_score():
    result = compute_c_score(make_user())
    assert result["c_score"] == 0

def test_empty_user_all_fields_zero():
    result = compute_c_score(make_user())
    assert result["dsa_done"] == 0
    assert result["lc_total"] == 0
    assert result["active_days"] == 0
    assert result["total_solved"] == 0


# --- Score cap at 999 ---

def test_score_capped_at_999():
    user = make_user(
        progress={str(i): {"done": True, "timestamp": None} for i in range(450)},
        external_totals={
            "LeetCode": 500,
            "LeetCode_Easy": 200,
            "LeetCode_Medium": 200,
            "LeetCode_Hard": 100,
            "LeetCode_Rating": 2500,
            "GFG": 100,
            "HackerRank": 100,
            "Coding Ninjas": 100,
        },
        external_daily_counts={f"2024-{str(i).zfill(3)}": 1 for i in range(1, 366)},
    )
    result = compute_c_score(user)
    assert result["c_score"] <= 999


# --- Negative external values ---

def test_negative_lc_total_does_not_raise():
    user = make_user(external_totals={"LeetCode": -50})
    result = compute_c_score(user)
    assert result["c_score"] >= 0

def test_negative_external_totals_not_counted_in_total_solved():
    user = make_user(external_totals={
        "LeetCode": -100,
        "GFG": -50,
        "HackerRank": -10,
        "Coding Ninjas": -5,
    })
    result = compute_c_score(user)
    # global_total uses max(..., 0) so negatives should not drag total below 0
    assert result["total_solved"] >= 0

def test_negative_lc_rating_gives_zero_rating_score():
    user = make_user(external_totals={"LeetCode_Rating": -500})
    result = compute_c_score(user)
    assert result["c_score"] >= 0


# --- Mixed in-app and external progress ---

def test_dsa_progress_only():
    progress = {str(i): {"done": True, "timestamp": None} for i in range(225)}
    result = compute_c_score(make_user(progress=progress))
    assert result["dsa_done"] == 225
    assert result["c_score"] == int(round((225 / 450) * 250))

def test_external_only_no_dsa():
    user = make_user(external_totals={
        "LeetCode": 250,
        "LeetCode_Easy": 100,
        "LeetCode_Medium": 50,
        "LeetCode_Hard": 20,
        "LeetCode_Rating": 1500,
        "GFG": 50,
        "HackerRank": 0,
        "Coding Ninjas": 0,
    })
    result = compute_c_score(user)
    assert result["dsa_done"] == 0
    assert result["c_score"] > 0

def test_mixed_dsa_and_external():
    progress = {str(i): {"done": True, "timestamp": None} for i in range(100)}
    user = make_user(
        progress=progress,
        external_totals={"LeetCode": 100, "GFG": 50, "HackerRank": 0, "Coding Ninjas": 0},
    )
    result = compute_c_score(user)
    assert result["dsa_done"] == 100
    assert result["lc_total"] == 100
    assert result["total_solved"] == 150


def test_total_solved_uses_platform_maxes_when_questions_are_available():
    progress = {
        "lc1": {"done": True},
        "lc2": {"done": True},
        "other": {"done": True},
    }
    questions = [
        {"_id": "lc1", "url": "https://leetcode.com/problems/two-sum/"},
        {"_id": "lc2", "url": "https://leetcode.com/problems/binary-search/"},
        {"_id": "other", "url": "https://example.com/problem"},
    ]

    total = compute_total_solved(progress, {"LeetCode": 2, "GFG": 5}, questions)

    assert total == 8


def test_total_solved_fallback_does_not_add_overlapping_dsa_and_external_counts():
    progress = {str(index): {"done": True} for index in range(10)}

    total = compute_total_solved(progress, {"LeetCode": 10})

    assert total == 10


# --- Active day consistency ---

def test_active_days_from_external_daily_counts():
    user = make_user(external_daily_counts={
        "2024-01-01": 3,
        "2024-01-02": 1,
        "2024-01-03": 5,
    })
    result = compute_c_score(user)
    assert result["active_days"] == 3

def test_active_days_full_year_maxes_consistency():
    dates = {f"2024-{str(i).zfill(3)}": 1 for i in range(1, 366)}
    user = make_user(external_daily_counts=dates)
    result = compute_c_score(user)
    assert result["active_days"] == 365
    # consistency component should be fully maxed (100 pts)
    assert result["c_score"] >= 100


# --- Return structure ---

def test_return_keys_present():
    result = compute_c_score(make_user())
    expected_keys = {
        "c_score", "dsa_done", "lc_total", "lc_easy", "lc_medium",
        "lc_hard", "lc_rating", "gfg_total", "hr_total", "cn_total",
        "active_days", "total_solved",
    }
    assert expected_keys == set(result.keys())
