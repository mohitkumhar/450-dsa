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


class FakeXssUniversityResponse:
    status_code = 200

    def json(self):
        return [
            {"name": "University of <script>alert('xss')</script> Testing", "country": "<b>India</b>"},
            {"name": "A&B University", "country": "India"},
            {"name": 'Test "Quoted" University', "country": "India"},
            {"name": "Safe University", "country": "Normal"},
        ]


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(profile_bp)
    return app


def test_university_search_uses_https_and_params(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeUniversityResponse()

    monkeypatch.setattr(profile_routes.requests, "get", fake_get)

    app = _make_app()
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


def test_university_search_returns_html_special_chars_unescaped(monkeypatch):
    def fake_get(url, **kwargs):
        return FakeXssUniversityResponse()

    monkeypatch.setattr(profile_routes.requests, "get", fake_get)

    app = _make_app()
    response = app.test_client().get("/search_universities?q=test")
    data = response.get_json()

    assert response.status_code == 200
    assert len(data) == 4

    assert data[0] == {
        "name": "University of <script>alert('xss')</script> Testing",
        "country": "<b>India</b>",
        "label": "University of <script>alert('xss')</script> Testing, <b>India</b>",
    }
    assert data[1] == {"name": "A&B University", "country": "India", "label": "A&B University, India"}
    assert data[2] == {"name": 'Test "Quoted" University', "country": "India", "label": 'Test "Quoted" University, India'}
    assert data[3] == {"name": "Safe University", "country": "Normal", "label": "Safe University, Normal"}
