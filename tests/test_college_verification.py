import app.admin.routes as admin_routes
import app.profile.routes as profile_routes
from app.college_verification import build_college_verification_updates, parse_college_domain_allowlist
from conftest import build_test_app, login_test_user


def test_parse_college_domain_allowlist_handles_json_mapping():
    allowlist = parse_college_domain_allowlist(
        '{"Alpha University": ["alpha.edu", "mail.alpha.edu"], "Ignored": 1}'
    )

    assert allowlist == {
        "alpha university": ["alpha.edu", "mail.alpha.edu"],
    }


def test_build_college_verification_updates_verifies_matching_domain():
    updates = build_college_verification_updates(
        college="Alpha University",
        email="student@alpha.edu",
        allowlist={"alpha university": ["alpha.edu"]},
    )

    assert updates == {
        "college_verification_status": "verified",
        "college_verification_method": "domain",
    }


def test_build_college_verification_updates_preserves_admin_verification():
    updates = build_college_verification_updates(
        college="Alpha University",
        email="student@elsewhere.com",
        allowlist={"alpha university": ["alpha.edu"]},
        previous_college=" alpha   university ",
        previous_status="verified",
        previous_method="admin",
    )

    assert updates == {
        "college_verification_status": "verified",
        "college_verification_method": "admin",
    }


def test_edit_profile_marks_college_pending_when_domain_does_not_match(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, admin_routes),
    )
    flask_app.config["COLLEGE_DOMAIN_ALLOWLIST"] = {
        "alpha university": ["alpha.edu"],
    }
    user_id = test_db.user.insert_one(
        {
            "name": "Student",
            "email": "student@example.com",
            "progress": {},
            "is_admin": False,
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post(
            "/edit_profile",
            json={"name": "Student", "college": "Alpha University"},
        )

    user = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert user["college"] == "Alpha University"
    assert user["college_verification_status"] == "pending"
    assert user["college_verification_method"] == ""


def test_edit_profile_auto_verifies_matching_college_domain(monkeypatch):
    flask_app, test_db = build_test_app(
        monkeypatch,
        extra_db_targets=(profile_routes, admin_routes),
    )
    flask_app.config["COLLEGE_DOMAIN_ALLOWLIST"] = {
        "alpha university": ["alpha.edu"],
    }
    user_id = test_db.user.insert_one(
        {
            "name": "Student",
            "email": "student@alpha.edu",
            "progress": {},
            "is_admin": False,
        }
    ).inserted_id

    with flask_app.test_client() as client:
        login_test_user(client, user_id)
        response = client.post(
            "/edit_profile",
            json={"name": "Student", "college": "Alpha University"},
        )

    user = test_db.user.find_one({"_id": user_id})
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert user["college_verification_status"] == "verified"
    assert user["college_verification_method"] == "domain"
