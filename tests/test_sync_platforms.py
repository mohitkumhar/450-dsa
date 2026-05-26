from flask import Flask
from types import SimpleNamespace

import app.profile.routes as profile_routes
import app.profile.sync_service as profile_sync_service
from app.profile.routes import profile_bp


def create_profile_test_app():
    app = Flask(__name__)
    app.config.update(
        LOGIN_DISABLED=True,
        RATELIMIT_ENABLED=False,
        SECRET_KEY="test-secret",
        TESTING=True,
    )
    app.register_blueprint(profile_bp)
    return app


def test_sync_platforms_rejects_missing_json_body():
    app = create_profile_test_app()

    response = app.test_client().post("/sync_platforms")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }


def test_sync_platforms_rejects_malformed_json_body():
    app = create_profile_test_app()

    response = app.test_client().post(
        "/sync_platforms",
        data="{bad json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }


def test_sync_platforms_rejects_non_object_json_body():
    app = create_profile_test_app()

    response = app.test_client().post("/sync_platforms", json=["leetcode"])

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object.",
    }


def test_sync_platforms_runs_selected_platform_jobs_concurrently(monkeypatch):
    app = create_profile_test_app()
    captured = {}

    monkeypatch.setattr(
        profile_routes,
        "current_user",
        SimpleNamespace(
            id="user-1",
            is_authenticated=True,
            last_sync=None,
            leetcode_username="",
            github_username="",
            gfg_username="",
            hackerrank_username="",
            codingninjas_username="",
            atcoder_username="",
            reload=lambda: None,
        ),
    )
    monkeypatch.setattr(
        profile_routes,
        "db",
        SimpleNamespace(user=SimpleNamespace(update_one=lambda query, update: captured.setdefault("db_update", (query, update)))),
    )
    monkeypatch.setattr(
        profile_routes.cache,
        "delete",
        lambda key: captured.setdefault("cleared_cache_key", key),
    )

    def fake_run_fetch_jobs(fetch_jobs, max_workers=5):
        captured["job_names"] = sorted(fetch_jobs.keys())
        captured["max_workers"] = max_workers
        return (
            {
                "leetcode": {
                    "stats": {
                        "calendar": {"2026-05-25": 2},
                        "total": 101,
                        "difficulty": {"Easy": 40, "Medium": 50, "Hard": 11},
                        "contest": {"attendedContestsCount": 5, "rating": 1800, "globalRanking": 1234},
                    },
                    "rating_history": [{"x": "2026-05-25", "y": 1800}],
                    "badges": [{"name": "Knight"}],
                },
                "github": {"calendar": {"2026-05-25": 3}, "stats": {"issues": 4, "prs": 5, "merged_prs": 2, "commits": 9}},
                "gfg": {"total": 77},
                "codingninjas": {"total": 12},
                "hackerrank": ([{"name": "Problem Solving", "stars": 5}], 44),
                "atcoder": {"total": 8},
            },
            {},
        )

    monkeypatch.setattr(profile_sync_service, "run_fetch_jobs", fake_run_fetch_jobs)

    response = app.test_client().post(
        "/sync_platforms",
        json={
            "leetcode": "lc-user",
            "github": "gh-user",
            "gfg": "gfg-user",
            "codingninjas": "cn-user",
            "hackerrank": "hr-user",
            "atcoder": "ac-user",
        },
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert captured["job_names"] == ["atcoder", "codingninjas", "gfg", "github", "hackerrank", "leetcode"]
    assert captured["max_workers"] == 4
    assert payload["success"] is True
    assert payload["platforms"]["leetcode"]["status"] == "synced"
    assert payload["platforms"]["github"]["status"] == "synced"
    assert payload["platforms"]["hackerrank"]["status"] == "synced"

    update_fields = captured["db_update"][1]["$set"]
    assert update_fields["external_daily_counts"] == {"2026-05-25": 5}
    assert update_fields["external_totals"]["LeetCode"] == 101
    assert update_fields["external_totals"]["GitHub_Commits"] == 9
    assert update_fields["external_totals"]["GFG"] == 77
    assert update_fields["external_totals"]["Coding Ninjas"] == 12
    assert update_fields["external_totals"]["HackerRank"] == 44
    assert update_fields["external_totals"]["AtCoder"] == 8
    assert update_fields["rating_history"] == [{"x": "2026-05-25", "y": 1800}]
    assert update_fields["lc_badges_json"] == '[{"name": "Knight"}]'
    assert update_fields["hr_badges_json"] == '[{"name": "Problem Solving", "stars": 5}]'


def test_sync_platforms_tolerates_missing_cache_extension(monkeypatch):
    app = create_profile_test_app()
    captured = {}

    monkeypatch.setattr(
        profile_routes,
        "current_user",
        SimpleNamespace(
            id="user-1",
            is_authenticated=True,
            last_sync=None,
            leetcode_username="",
            github_username="",
            gfg_username="",
            hackerrank_username="",
            codingninjas_username="",
            atcoder_username="",
            reload=lambda: None,
        ),
    )
    monkeypatch.setattr(
        profile_routes,
        "db",
        SimpleNamespace(user=SimpleNamespace(update_one=lambda query, update: captured.setdefault("db_update", (query, update)))),
    )

    monkeypatch.setattr(
        profile_sync_service,
        "run_fetch_jobs",
        lambda fetch_jobs, max_workers=5: (
            {
                "leetcode": {
                    "stats": {
                        "calendar": {"2026-05-25": 1},
                        "total": 1,
                        "difficulty": {"Easy": 1, "Medium": 0, "Hard": 0},
                        "contest": {"attendedContestsCount": 0, "rating": 1500, "globalRanking": 1},
                    }
                }
            },
            {},
        ),
    )

    response = app.test_client().post("/sync_platforms", json={"leetcode": "lc-user"})

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_sync_platforms_marks_github_rate_limit_payload_failed(monkeypatch):
    app = create_profile_test_app()
    captured = {}

    monkeypatch.setattr(
        profile_routes,
        "current_user",
        SimpleNamespace(
            id="user-1",
            is_authenticated=True,
            last_sync=None,
            leetcode_username="",
            github_username="",
            gfg_username="",
            hackerrank_username="",
            codingninjas_username="",
            atcoder_username="",
            reload=lambda: None,
        ),
    )
    monkeypatch.setattr(
        profile_routes,
        "db",
        SimpleNamespace(user=SimpleNamespace(update_one=lambda query, update: captured.setdefault("db_update", (query, update)))),
    )
    monkeypatch.setattr(
        profile_routes.cache,
        "delete",
        lambda key: captured.setdefault("cleared_cache_key", key),
    )
    monkeypatch.setattr(
        profile_sync_service,
        "run_fetch_jobs",
        lambda fetch_jobs, max_workers=5: (
            {"github": {"error": "rate_limited", "calendar": {"2026-05-25": 3}, "stats": None}},
            {},
        ),
    )

    response = app.test_client().post(
        "/sync_platforms",
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
        json={"github": "octocat"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"] == "Sync failed for all platforms."
    assert payload["platforms"]["github"] == {
        "status": "failed",
        "error": "GitHub API rate limit reached. Please try again later.",
    }
    update_fields = captured["db_update"][1]["$set"]
    assert update_fields["external_daily_counts"] == {}
    assert "GitHub_Commits" not in update_fields["external_totals"]
