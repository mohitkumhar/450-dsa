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

    if 'ui_theme' in data:
        theme = data['ui_theme']
        if not isinstance(theme, str):
            return None, 'ui_theme must be text'
        theme = theme.strip().lower()
        if theme not in {'dark', 'light'}:
            return None, 'ui_theme must be one of: dark, light'
        update_fields['ui_theme'] = theme

    if 'accent_color' in data:
        accent_color = data['accent_color']
        if not isinstance(accent_color, str):
            return None, 'accent_color must be text'
        accent_color = accent_color.strip()
        if not re.fullmatch(r'^#[0-9A-Fa-f]{6}$', accent_color):
            return None, 'accent_color must be a valid hex color'
        update_fields['accent_color'] = accent_color

    if 'compact_mode' in data:
        compact_mode = data['compact_mode']
        if isinstance(compact_mode, str):
            compact_mode = compact_mode.strip().lower()
            if compact_mode in {'true', '1', 'yes', 'on'}:
                compact_mode = True
            elif compact_mode in {'false', '0', 'no', 'off'}:
                compact_mode = False
            else:
                return None, 'compact_mode must be a boolean'
        elif not isinstance(compact_mode, bool):
            return None, 'compact_mode must be a boolean'
        update_fields['compact_mode'] = compact_mode

    if 'chart_palette' in data:
        palette = data['chart_palette']
        if not isinstance(palette, str):
            return None, 'chart_palette must be text'
        palette = palette.strip().lower()
        if palette not in {'default', 'cool', 'warm', 'monochrome'}:
            return None, 'chart_palette must be one of: default, cool, warm, monochrome'
        update_fields['chart_palette'] = palette

    return update_fields, None


def validate_username(username):
    """Reject usernames containing characters dangerous in JavaScript string contexts."""
    if not username:
        return username
    if re.search(r"['\"\\<>\n\r]|</", username):
        raise ValueError("Username contains invalid characters")
    return username
