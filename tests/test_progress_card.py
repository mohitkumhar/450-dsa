"""Tests for the progress card generation route."""
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from bson.objectid import ObjectId

import pytest


class FakeCollection:
    """Mock MongoDB collection for testing."""
    def __init__(self):
        self.data = {}

    def find_one(self, query):
        """Mock find_one to return test user data."""
        if "_id" in query:
            return self.data.get(str(query["_id"]))
        return None

    def insert_one(self, doc):
        """Mock insert_one."""
        return SimpleNamespace(inserted_id=ObjectId())


class FakeDB:
    """Mock MongoDB database for testing."""
    def __init__(self):
        self.user = FakeCollection()
        self.topic = FakeCollection()
        self.question = FakeCollection()


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    from app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Create a mock database."""
    return FakeDB()


def test_public_card_valid_user(client, mock_db):
    """Test that /u/<user_id>/card.png returns 200 with valid user."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Test User",
        "c_score": 100,
        "dsa_progress": 50,
        "current_streak": 5,
        "platforms": {
            "LeetCode": 10,
            "GFG": 5,
        }
    }
    
    mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert len(response.data) > 0


def test_public_card_invalid_user_id(client):
    """Test that /u/<invalid_id>/card.png returns 400."""
    response = client.get("/u/invalid_id/card.png")
    assert response.status_code == 400
    assert b"Invalid User ID" in response.data


def test_public_card_missing_user(client, mock_db):
    """Test that /u/<nonexistent_user_id>/card.png returns 404."""
    user_id = ObjectId()
    
    with patch('app.profile.routes.db', mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        assert response.status_code == 404
        assert b"User not found" in response.data


def test_public_card_with_minimal_data(client, mock_db):
    """Test that card generation works with minimal user data."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Minimal User",
        # Missing optional fields
    }
    
    mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        assert response.status_code == 200
        assert response.content_type == "image/png"


def test_public_card_with_anonymous_name(client, mock_db):
    """Test that card generation works when user has no name."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        # No name field
        "c_score": 50,
        "dsa_progress": 25,
        "current_streak": 2,
        "platforms": {}
    }
    
    mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        assert response.status_code == 200
        assert response.content_type == "image/png"


def test_card_generator_returns_bytesio():
    """Test that generate_progress_card returns a BytesIO object."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="Test User",
        c_score=100,
        dsa_progress=75,
        current_streak=10,
        platforms={"LeetCode": 50}
    )    
    assert isinstance(result, io.BytesIO)    
    result.seek(0)
    png_header = result.read(8)
    assert png_header == b'\x89PNG\r\n\x1a\n', "BytesIO should contain valid PNG data"
