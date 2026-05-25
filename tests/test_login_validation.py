import app.auth.routes as auth_routes
from conftest import build_test_app


def test_login_missing_password_returns_form_error_instead_of_500(monkeypatch):
    flask_app, test_db = build_test_app(monkeypatch)
    monkeypatch.setattr(auth_routes, "db", test_db)

    hashed_password = auth_routes.bcrypt.generate_password_hash("StrongPass1!").decode("utf-8")
    test_db.user.insert_one(
        {
            "name": "Login User",
            "email": "login@example.com",
            "password": hashed_password,
            "progress": {},
            "is_admin": False,
        }
    )

    with flask_app.test_client() as client:
        response = client.post("/login", data={"email": "login@example.com"})

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Login unsuccessful. Please check email and password." in html


def test_login_missing_email_returns_form_error_instead_of_500(monkeypatch):
    flask_app, _ = build_test_app(monkeypatch)

    with flask_app.test_client() as client:
        response = client.post("/login", data={"password": "StrongPass1!"})

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Login unsuccessful. Please check email and password." in html
