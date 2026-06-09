from urllib.parse import urlparse


import re

PROFILE_FIELD_LIMITS = {
    'name': 100,
    'bio': 500,
    'location': 100,
    'college': 200,
    'headline': 150,
    'linkedin_url': 300,
    'twitter_url': 300,
    'website_url': 300,
    'resume_url': 300,
}

PROFILE_URL_FIELDS = {'linkedin_url', 'twitter_url', 'website_url', 'resume_url'}

PROFILE_VISIBILITY_OPTIONS = {'public', 'private', 'stats_only'}


def build_profile_updates(data):
    update_fields = {}

    for field, max_length in PROFILE_FIELD_LIMITS.items():
        if field not in data:
            continue

        value = data[field]
        if value is None:
            update_fields[field] = ''
            continue

        if not isinstance(value, str):
            return None, f'{field} must be text'

        value = value.strip()

        if field == 'name' and not value:
            return None, 'name is required'

        if len(value) > max_length:
            return None, f'{field} must be at most {max_length} characters'

        if field in PROFILE_URL_FIELDS and value:
            url_val = value.strip()
            parsed_raw = urlparse(url_val)

            if parsed_raw.scheme:
                if parsed_raw.scheme not in {'http', 'https'}:
                    return None, f'Invalid URL for {field}'
            else:
                if '//' in url_val:
                    url_val = 'https:' + url_val if url_val.startswith('//') else 'https://' + url_val.split('//', 1)[1]
                else:
                    url_val = 'https://' + url_val

            parsed = urlparse(url_val)

            if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                return None, f'Invalid URL for {field}'

            value = url_val

        update_fields[field] = value
    if 'profile_visibility' in data:
        visibility = data['profile_visibility']

        if not isinstance(visibility, str):
            return None, 'profile_visibility must be text'

        visibility = visibility.strip().lower()

        if visibility not in PROFILE_VISIBILITY_OPTIONS:
            return None, 'profile_visibility must be one of: public, private, stats_only'

        update_fields['profile_visibility'] = visibility

    return update_fields, None


def validate_username(username):
    """Reject usernames containing characters dangerous in JavaScript string contexts."""
    if not username:
        return username
    if re.search(r"['\"\\<>\n\r]|</", username):
        raise ValueError("Username contains invalid characters")
    return username
