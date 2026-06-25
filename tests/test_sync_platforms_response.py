from app.profile.routes import build_sync_platforms_response


def test_sync_platforms_response_partial_success():
    platform_status = {
        "leetcode": {"status": "failed", "error": "timeout"},
        "github": {"status": "synced"},
        "gfg": {"status": "skipped"},
        "codingninjas": {"status": "skipped"},
        "hackerrank": {"status": "skipped"},
    }
    result = build_sync_platforms_response(platform_status)
    assert result["success"] is True
    assert result["partial_success"] is True
    assert result["platforms"]["leetcode"]["status"] == "failed"


def test_sync_platforms_response_all_failed():
    platform_status = {
        "leetcode": {"status": "failed", "error": "timeout"},
        "github": {"status": "failed", "error": "not found"},
    }
    result = build_sync_platforms_response(platform_status)
    assert result["success"] is False
    assert "all platforms" in result["error"].lower()


def test_sync_platforms_response_none_attempted():
    platform_status = {
        "leetcode": {"status": "skipped"},
        "github": {"status": "skipped"},
    }
    result = build_sync_platforms_response(platform_status)
    assert result["success"] is False
    assert "no platforms" in result["error"].lower()

