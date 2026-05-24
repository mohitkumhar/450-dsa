from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def read_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def test_topic_template_uses_data_driven_endpoints():
    topic = read_template("topic.html")

    assert 'id="topic-endpoints"' in topic
    assert "data-update-question-url-template" in topic
    assert "data-login-url" in topic
    assert "fetch(buildUpdateQuestionUrl(id)" in topic
    assert "window.location.href = loginUrl;" in topic


def test_bookmarks_template_uses_data_driven_update_endpoint():
    bookmarks = read_template("bookmarks.html")

    assert 'id="bookmarks-endpoints"' in bookmarks
    assert "data-update-question-url-template" in bookmarks
    assert "fetch(buildUpdateQuestionUrl(id)" in bookmarks


def test_profile_template_uses_data_driven_profile_endpoints():
    profile = read_template("profile.html")

    assert 'id="profile-endpoints"' in profile
    assert "data-edit-profile-url" in profile
    assert "data-sync-platforms-url" in profile
    assert "data-upload-photo-url" in profile
    assert "data-search-universities-url" in profile
    assert "profileEndpoints.dataset.editProfileUrl" in profile
    assert "profileEndpoints.dataset.syncPlatformsUrl" in profile
    assert "profileEndpoints.dataset.uploadPhotoUrl" in profile
    assert "profileEndpoints.dataset.searchUniversitiesUrl" in profile
