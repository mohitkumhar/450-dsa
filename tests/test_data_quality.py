from data_quality import (
    ALLOWED_DUPLICATE_PROBLEMS,
    ALLOWED_DUPLICATE_URLS,
    duplicate_groups,
    load_data,
    normalize_problem,
    normalize_url,
    unexpected_duplicate_groups,
)


def test_seed_data_has_no_unexpected_duplicate_problems_or_urls():
    unexpected = unexpected_duplicate_groups(load_data())

    assert unexpected == {"problems": {}, "urls": {}, "url2s": {}}


def test_known_cross_topic_duplicates_are_documented():
    data = load_data()
    problem_duplicates = duplicate_groups(data, "problem", normalize_problem)
    url_duplicates = duplicate_groups(data, "url", normalize_url)

    assert "subset sum problem" in problem_duplicates
    assert "subset sum problem" in ALLOWED_DUPLICATE_PROBLEMS
    assert "https://practice.geeksforgeeks.org/problems/kadanes-algorithm/0" in url_duplicates
    assert "https://practice.geeksforgeeks.org/problems/kadanes-algorithm/0" in ALLOWED_DUPLICATE_URLS


def test_url_normalization_ignores_query_strings_and_trailing_slashes():
    assert (
        normalize_url("https://www.codingninjas.com/codestudio/problems/create-a-graph-and-print-it_1214551?topList=love-babbar-dsa-sheet-problems")
        == "https://www.codingninjas.com/codestudio/problems/create-a-graph-and-print-it_1214551"
    )
    assert (
        normalize_url("https://www.geeksforgeeks.org/minimize-cash-flow-among-given-set-friends-borrowed-money/")
        == "https://www.geeksforgeeks.org/minimize-cash-flow-among-given-set-friends-borrowed-money"
    )
