from flask import Flask
from types import SimpleNamespace

import app.profile.routes as profile_routes
from app.profile.routes import profile_bp


def create_profile_test_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True, SECRET_KEY="test-secret")
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

    monkeypatch.setattr(profile_routes, "run_fetch_jobs", fake_run_fetch_jobs)

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
