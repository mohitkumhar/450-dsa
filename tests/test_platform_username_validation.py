from app.utils import normalize_platform_username, platform_profile_url


def test_normalize_platform_username_accepts_supported_profile_urls():
    assert normalize_platform_username("github", "https://github.com/octocat") == "octocat"
    assert normalize_platform_username("leetcode", "https://leetcode.com/u/two-sum") == "two-sum"
    assert (
        normalize_platform_username(
            "codingninjas",
            "https://www.naukri.com/code360/profile/cn-user",
        )
        == "cn-user"
    )


def test_normalize_platform_username_rejects_unsafe_values():
    for platform, value in (
        ("github", "bad/user"),
        ("leetcode", "javascript:alert(1)"),
        ("gfg", "two words"),
        ("atcoder", "https://evil.example/user"),
    ):
        try:
            normalize_platform_username(platform, value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{platform} should reject {value!r}")


def test_platform_profile_url_returns_placeholder_for_invalid_stored_values():
    assert platform_profile_url("bad/user", "github") == "#"
    assert platform_profile_url("javascript:alert(1)", "leetcode") == "#"
