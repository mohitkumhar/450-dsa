from profile_validation import build_profile_updates


def test_profile_updates_trim_text_and_accept_https_urls():
    updates, error = build_profile_updates({
        'name': '  Saurabh  ',
        'bio': 'Building AI systems',
        'website_url': 'https://example.com/portfolio',
    })

    assert error is None
    assert updates == {
        'name': 'Saurabh',
        'bio': 'Building AI systems',
        'website_url': 'https://example.com/portfolio',
    }


def test_profile_updates_reject_blank_name():
    updates, error = build_profile_updates({'name': '   '})

    assert updates is None
    assert error == 'name is required'


def test_profile_updates_reject_overlong_text():
    updates, error = build_profile_updates({'bio': 'x' * 501})

    assert updates is None
    assert error == 'bio must be at most 500 characters'


def test_profile_updates_reject_javascript_urls():
    updates, error = build_profile_updates({'linkedin_url': 'javascript:alert(1)'})

    assert updates is None
    assert error == 'Invalid URL for linkedin_url'


def test_profile_updates_reject_non_text_values():
    updates, error = build_profile_updates({'headline': {'nested': 'value'}})

    assert updates is None
    assert error == 'headline must be text'
