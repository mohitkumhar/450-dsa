import json


def normalize_college_name(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip().lower()


def normalize_email_domain(email):
    if not isinstance(email, str) or "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def parse_college_domain_allowlist(raw_value):
    if not raw_value:
        return {}

    try:
        data = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}

    if not isinstance(data, dict):
        return {}

    allowlist = {}
    for college, domains in data.items():
        normalized_college = normalize_college_name(college)
        if not normalized_college:
            continue

        if isinstance(domains, str):
            domains = [domains]
        if not isinstance(domains, list):
            continue

        normalized_domains = sorted(
            {
                domain.strip().lower()
                for domain in domains
                if isinstance(domain, str) and domain.strip()
            }
        )
        if normalized_domains:
            allowlist[normalized_college] = normalized_domains

    return allowlist


def build_college_verification_updates(
    *,
    college,
    email,
    allowlist,
    previous_college="",
    previous_status="",
    previous_method="",
):
    normalized_college = normalize_college_name(college)
    if not normalized_college:
        return {
            "college_verification_status": "",
            "college_verification_method": "",
        }

    if (
        previous_status == "verified"
        and previous_method == "admin"
        and normalize_college_name(previous_college) == normalized_college
    ):
        return {
            "college_verification_status": "verified",
            "college_verification_method": "admin",
        }

    email_domain = normalize_email_domain(email)
    allowed_domains = allowlist.get(normalized_college, [])
    if email_domain and email_domain in allowed_domains:
        return {
            "college_verification_status": "verified",
            "college_verification_method": "domain",
        }

    return {
        "college_verification_status": "pending",
        "college_verification_method": "",
    }
