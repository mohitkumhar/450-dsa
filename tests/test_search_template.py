from pathlib import Path


SEARCH_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "search.html"
SEARCH_JS = Path(__file__).resolve().parents[1] / "static" / "js" / "search.js"


def test_search_platform_prompt_includes_each_chip_label():
    js_content = SEARCH_JS.read_text(encoding="utf-8")

    assert "leetcode: 'LeetCode'" in js_content
    assert "gfg: 'GFG'" in js_content
    assert "cn: 'Coding Ninjas'" in js_content
    assert "hackerrank: 'HackerRank'" in js_content


def test_search_empty_input_uses_active_platform_prompt():
    js_content = SEARCH_JS.read_text(encoding="utf-8")

    assert "function renderPlatformPrompt()" in js_content
    assert "if (activeToken) {\n      renderPlatformPrompt();" in js_content
    assert "Type a search term to find ${platform} practice links." in js_content


def test_search_template_includes_recent_search_storage_and_panel():
    template = SEARCH_TEMPLATE.read_text(encoding="utf-8")
    js_content = SEARCH_JS.read_text(encoding="utf-8")

    assert "id=\"recentSearches\"" in template
    assert "const RECENT_SEARCHES_KEY = 'dsa_recent_searches_v1';" in js_content
    assert "const MAX_RECENT_SEARCHES = 5;" in js_content
    assert "function rememberRecentSearch(text, token)" in js_content
    assert "function applyRecentSearch(index)" in js_content
    assert "renderRecentSearches();" in js_content
