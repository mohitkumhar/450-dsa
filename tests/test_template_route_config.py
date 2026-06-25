from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def test_profile_template_uses_url_for_endpoint_config():
    template = (TEMPLATE_DIR / "profile.html").read_text(encoding="utf-8")

    assert '"editProfile": url_for(\'profile.edit_profile\')' in template
    assert '"syncPlatforms": url_for(\'profile.sync_platforms\')' in template
    assert '"searchUniversities": url_for(\'profile.search_universities\')' in template
    assert '"publicCardPath": url_for(\'profile.public_card\'' in template
    assert "fetch('/edit_profile'" not in template
    assert "fetch('/sync_platforms'" not in template
    assert "fetch('/search_universities?q='" not in template
    assert "window.location.origin + '/u/" not in template


def test_tracker_templates_use_configured_update_question_route():
    topic_template = (TEMPLATE_DIR / "topic.html").read_text(encoding="utf-8")
    bookmarks_template = (TEMPLATE_DIR / "bookmarks.html").read_text(encoding="utf-8")

    assert '"updateQuestionBase": url_for(\'tracker.update_question\'' in topic_template
    assert '"updateQuestionBase": url_for(\'tracker.update_question\'' in bookmarks_template
    assert "fetch('/update_question/' + id" not in topic_template
    assert "fetch('/update_question/' + id" not in bookmarks_template


def test_search_and_leaderboard_templates_use_url_for_route_config():
    search_template = (TEMPLATE_DIR / "search.html").read_text(encoding="utf-8")
    leaderboard_template = (TEMPLATE_DIR / "leaderboard.html").read_text(encoding="utf-8")

    assert '"searchQuestions": url_for(\'search.api_search_questions\')' in search_template
    assert "fetch(`/api/search_questions?q=${encodeURIComponent(query)}`" not in search_template

    assert '"publicProfileBase": url_for(\'public.public_profile\'' in leaderboard_template
    assert "`/u/${encodeURIComponent(e.user_id)}`" not in leaderboard_template
