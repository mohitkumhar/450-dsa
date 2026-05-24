from flask import Flask

import app.profile.routes as profile_routes
from app.profile import profile_bp


class FakeUniversityResponse:
    status_code = 200

    def json(self):
        return [
            {"name": "A&B University", "country": "India"},
            {"name": "A&B University", "country": "India"},
            {"name": "A and B College", "country": "India"},
        ]


def test_university_search_uses_https_and_params(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeUniversityResponse()

    monkeypatch.setattr(profile_routes.requests, "get", fake_get)

    app = Flask(__name__)
    app.register_blueprint(profile_bp)

    response = app.test_client().get("/search_universities?q=A%26B University")

    assert response.status_code == 200
    assert calls == [
        (
            "https://universities.hipolabs.com/search",
            {"params": {"name": "A&B University"}, "timeout": 5},
        )
    ]
    assert response.get_json() == [
        {"name": "A&B University", "country": "India", "label": "A&B University, India"},
        {"name": "A and B College", "country": "India", "label": "A and B College, India"},
    ]
