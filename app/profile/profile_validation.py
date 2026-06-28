import re

# Theme preferences validation
THEME_DENSITIES = {"comfortable", "compact"}
CHART_PALETTES = {"default", "pastel", "vivid", "colorblind"}
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _validate_theme_preferences(data):
    updates = {}
    errors = {}

    if "theme_accent" in data:
        accent = str(data["theme_accent"]).strip()
        if HEX_COLOR_PATTERN.match(accent):
            updates["theme_accent"] = accent.lower()
        else:
            errors["theme_accent"] = "Accent color must be a 6-digit hex value."

    if "theme_density" in data:
        density = str(data["theme_density"]).strip()
        if density in THEME_DENSITIES:
            updates["theme_density"] = density
        else:
            errors["theme_density"] = "Density must be comfortable or compact."

    if "theme_chart_palette" in data:
        palette = str(data["theme_chart_palette"]).strip()
        if palette in CHART_PALETTES:
            updates["theme_chart_palette"] = palette
        else:
            errors["theme_chart_palette"] = "Chart palette is not supported."

    return updates, errors


def build_profile_updates(data):
    updates = {}
    errors = {}

    # Validate basic profile fields
    if "name" in data:
        name = str(data["name"]).strip()
        if len(name) > 100:
            errors["name"] = "Name must be 100 characters or less."
        elif len(name) < 2:
            errors["name"] = "Name must be at least 2 characters."
        else:
            updates["name"] = name

    if "bio" in data:
        bio = str(data["bio"]).strip()
        if len(bio) > 500:
            errors["bio"] = "Bio must be 500 characters or less."
        else:
            updates["bio"] = bio

    if "location" in data:
        location = str(data["location"]).strip()
        if len(location) > 100:
            errors["location"] = "Location must be 100 characters or less."
        else:
            updates["location"] = location

    if "college" in data:
        college = str(data["college"]).strip()
        if len(college) > 200:
            errors["college"] = "College must be 200 characters or less."
        else:
            updates["college"] = college

    if "headline" in data:
        headline = str(data["headline"]).strip()
        if len(headline) > 150:
            errors["headline"] = "Headline must be 150 characters or less."
        else:
            updates["headline"] = headline

    if "linkedin_url" in data:
        linkedin_url = str(data["linkedin_url"]).strip()
        if len(linkedin_url) > 300:
            errors["linkedin_url"] = "LinkedIn URL must be 300 characters or less."
        elif linkedin_url and not linkedin_url.startswith(('http://', 'https://')):
            errors["linkedin_url"] = "LinkedIn URL must start with http:// or https://"
        else:
            updates["linkedin_url"] = linkedin_url

    if "twitter_url" in data:
        twitter_url = str(data["twitter_url"]).strip()
        if len(twitter_url) > 300:
            errors["twitter_url"] = "Twitter URL must be 300 characters or less."
        elif twitter_url and not twitter_url.startswith(('http://', 'https://')):
            errors["twitter_url"] = "Twitter URL must start with http:// or https://"
        else:
            updates["twitter_url"] = twitter_url

    if "website_url" in data:
        website_url = str(data["website_url"]).strip()
        if len(website_url) > 300:
            errors["website_url"] = "Website URL must be 300 characters or less."
        elif website_url and not website_url.startswith(('http://', 'https://')):
            errors["website_url"] = "Website URL must start with http:// or https://"
        else:
            updates["website_url"] = website_url

    if "resume_url" in data:
        resume_url = str(data["resume_url"]).strip()
        if len(resume_url) > 300:
            errors["resume_url"] = "Resume URL must be 300 characters or less."
        elif resume_url and not resume_url.startswith(('http://', 'https://')):
            errors["resume_url"] = "Resume URL must start with http:// or https://"
        else:
            updates["resume_url"] = resume_url

    if "profile_visibility" in data:
        visibility = str(data["profile_visibility"]).strip()
        if visibility in {"public", "private", "stats_only"}:
            updates["profile_visibility"] = visibility
        else:
            errors["profile_visibility"] = "Visibility must be public, private, or stats_only"

    # Validate theme preferences
    theme_updates, theme_errors = _validate_theme_preferences(data)
    updates.update(theme_updates)
    errors.update(theme_errors)

    if errors:
        return None, errors
    return updates, None