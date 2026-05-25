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


def test_search_template_includes_saved_search_management_hooks():
    template = SEARCH_TEMPLATE.read_text()

    assert "id=\"savedSearches\"" in template
    assert "const canManageSavedSearches =" in template
    assert "let savedSearches =" in template
    assert "function renderSavedSearches()" in template
    assert "async function saveCurrentSearch()" in template
    assert "async function renameSavedSearch(searchId)" in template
    assert "async function deleteSavedSearch(searchId)" in template
