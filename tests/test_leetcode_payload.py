from app.platforms.fetchers import build_leetcode_profile_payload


def test_leetcode_profile_payload_uses_graphql_variables():
    payload = build_leetcode_profile_payload("saurabhhhcodes")

    assert payload["variables"] == {"username": "saurabhhhcodes"}
    assert "matchedUser(username: $username)" in payload["query"]
    assert "userContestRanking(username: $username)" in payload["query"]
    assert "saurabhhhcodes" not in payload["query"]


def test_leetcode_profile_payload_keeps_special_characters_out_of_query_text():
    username = 'bad"user) { injected { id } } #'

    payload = build_leetcode_profile_payload(username)

    assert payload["variables"]["username"] == username
    assert username not in payload["query"]
    assert "injected" not in payload["query"]
