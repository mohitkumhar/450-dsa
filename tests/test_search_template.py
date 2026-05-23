from pathlib import Path


SEARCH_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "search.html"


def test_search_platform_prompt_includes_each_chip_label():
    template = SEARCH_TEMPLATE.read_text()

    assert "leetcode: 'LeetCode'" in template
    assert "gfg: 'GFG'" in template
    assert "cn: 'Coding Ninjas'" in template
    assert "hackerrank: 'HackerRank'" in template


def test_search_empty_input_uses_active_platform_prompt():
    template = SEARCH_TEMPLATE.read_text()

    assert "function renderPlatformPrompt()" in template
    assert "if (activeToken) {\n      renderPlatformPrompt();" in template
    assert "Type a search term to find ${platform} practice links." in template
