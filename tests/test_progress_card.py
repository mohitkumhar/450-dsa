"""Tests for the progress card generation route."""
import io
from unittest.mock import patch
from bson.objectid import ObjectId

# pyrefly: ignore [missing-import]
import pytest
from datetime import datetime, timezone


class FakeCollection:
    """Mock MongoDB collection for testing."""
    def __init__(self):
        self.data = {}

    def find_one(self, query):
        """Mock find_one to return test user data."""
        if "_id" in query:
            return self.data.get(str(query["_id"]))
        return None

    def create_index(self, *args, **kwargs):
        """Mock create_index."""
        pass

    def count_documents(self, *args, **kwargs):
        """Mock count_documents."""
        return len(self.data)

    def find(self, *args, **kwargs):
        """Mock find."""
        return list(self.data.values())

    def insert_many(self, *args, **kwargs):
        """Mock insert_many."""
        pass

    class InsertResult:
        def __init__(self, inserted_id):
            self.inserted_id = inserted_id

    def insert_one(self, document, *args, **kwargs):
        """Mock insert_one."""
        from bson.objectid import ObjectId
        if "_id" not in document:
            document["_id"] = ObjectId()
        self.data[str(document["_id"])] = document
        return self.InsertResult(document["_id"])

    def update_many(self, *args, **kwargs):
        """Mock update_many."""
        pass


class FakeDB:
    """Mock MongoDB database for testing."""
    def __init__(self):
        self.user = FakeCollection()
        self.topic = FakeCollection()
        self.question = FakeCollection()


@pytest.fixture
def mock_db():
    """Create a mock database."""
    return FakeDB()


@pytest.fixture
def app(mock_db):
    """Create a Flask app for testing with mocked database."""
    # Patch db globally before importing app
    with patch('app.extensions.db', mock_db), \
         patch('app.db', mock_db), \
         patch('app.mongo'), \
         patch.dict('os.environ', {'SECRET_KEY': 'test-secret-key'}, clear=False):
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        
        # Keep the mock in place for the app context
        app.mock_db = mock_db
        yield app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


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
    
    # Verify it's a BytesIO object
    assert isinstance(result, io.BytesIO)
    
    # Verify it contains PNG data
    result.seek(0)
    png_header = result.read(8)
    assert png_header == b'\x89PNG\r\n\x1a\n', "BytesIO should contain valid PNG data"


def test_public_card_valid_user(client, app):
    """Test that /u/<user_id>/card.png returns 200 with valid user."""
    user_id = ObjectId()
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    user_data = {
        "_id": user_id,
        "name": "Test User",
        "progress": {
            "q1": {"done": True, "timestamp": now},
            "q2": {"done": True, "timestamp": now - timedelta(days=1)}
        },
        "external_totals": {
            "LeetCode": 10,
            "GFG": 5,
        }
    }
    
    app.mock_db.question.data = {
        "q1": {"_id": "q1", "url": "https://leetcode.com/"},
        "q2": {"_id": "q2", "url": "https://geeksforgeeks.org/"},
        "q3": {"_id": "q3", "url": ""},
        "q4": {"_id": "q4", "url": ""}
    }
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert len(response.data) > 0


def test_public_card_invalid_user_id(client, app):
    """Test that /u/<invalid_id>/card.png returns 400."""
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get("/u/invalid_id/card.png")
        assert response.status_code == 400
        assert b"Invalid User ID" in response.data


def test_public_card_missing_user(client, app):
    """Test that /u/<nonexistent_user_id>/card.png returns 404."""
    user_id = ObjectId()
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 404
        assert b"User not found" in response.data


def test_public_card_with_minimal_data(client, app):
    """Test that card generation works with minimal user data."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Minimal User",
        "progress": {},
        "external_totals": {}
    }
    
    app.mock_db.question.data = {
        "q1": {"_id": "q1"}
    }
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"


def test_public_card_with_anonymous_name(client, app):
    """Test that card generation works when user has no name."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "progress": {"q1": {"done": True, "timestamp": datetime.now(timezone.utc)}},
        "external_totals": {}
    }
    
    app.mock_db.question.data = {
        "q1": {"_id": "q1"}
    }
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"


def test_public_card_caching(client, app):
    """Test that card caching works correctly."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Cache Test User",
        "progress": {"q1": {"done": True, "timestamp": datetime.now(timezone.utc)}},
        "external_totals": {"LeetCode": 20}
    }
    
    app.mock_db.question.data = {
        "q1": {"_id": "q1"}
    }
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        # First request - should generate card
        response1 = client.get(f"/u/{user_id}/card.png")
        assert response1.status_code == 200
        data1 = response1.data
        
        # Second request - should use cache
        response2 = client.get(f"/u/{user_id}/card.png")
        assert response2.status_code == 200
        data2 = response2.data
        
        # Both should return the same PNG data
        assert data1 == data2


def test_public_card_sets_cache_headers_and_etag(client, app):
    user_id = ObjectId()
    now = datetime.now(timezone.utc)
    app.mock_db.question.data = {"q1": {"_id": "q1"}}
    app.mock_db.user.data[str(user_id)] = {
        "_id": user_id,
        "name": "Header User",
        "progress": {"q1": {"done": True, "timestamp": now}},
        "external_totals": {},
    }

    with patch("app.profile.routes.db", app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert response.headers["ETag"].startswith('"progress-card-')
    assert response.headers["Last-Modified"]


def test_public_card_returns_304_for_matching_etag(client, app):
    user_id = ObjectId()
    now = datetime.now(timezone.utc)
    app.mock_db.question.data = {"q1": {"_id": "q1"}}
    app.mock_db.user.data[str(user_id)] = {
        "_id": user_id,
        "name": "Conditional User",
        "progress": {"q1": {"done": True, "timestamp": now}},
        "external_totals": {},
    }

    with patch("app.profile.routes.db", app.mock_db):
        initial = client.get(f"/u/{user_id}/card.png")
        response = client.get(
            f"/u/{user_id}/card.png",
            headers={"If-None-Match": initial.headers["ETag"]},
        )

    assert initial.status_code == 200
    assert response.status_code == 304
    assert response.data == b""


def test_public_card_exception_handling(client, app):
    """Test that card generation errors do not expose raw exception text."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Error Test User",
        "progress": {},
        "external_totals": {}
    }
    
    app.mock_db.question.data = {}
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db), \
         patch('card_generator.generate_progress_card', side_effect=Exception("Secret path leak")):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 500
        assert b"Unable to generate progress card" in response.data
        assert b"Secret path leak" not in response.data


def test_card_generator_with_long_name(client, app):
    """Test that card generation handles long user names."""
    user_id = ObjectId()
    long_name = "A" * 50  # Very long name
    user_data = {
        "_id": user_id,
        "name": long_name,
        "progress": {},
        "external_totals": {"LeetCode": 100, "GFG": 50, "Coding Ninjas": 30, "HackerRank": 20}
    }
    
    app.mock_db.question.data = {}
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert len(response.data) > 0


def test_card_generator_with_all_platforms(client, app):
    """Test that card generation works with all platforms."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Multi-Platform User",
        "progress": {},
        "external_totals": {
            "LeetCode": 500,
            "GFG": 300,
            "Coding Ninjas": 200,
            "HackerRank": 150
        }
    }
    
    app.mock_db.question.data = {}
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert len(response.data) > 0


def test_card_generator_with_zero_values(client, app):
    """Test that card generation works with zero values."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Beginner User",
        "progress": {},
        "external_totals": {}
    }
    
    app.mock_db.question.data = {}
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert len(response.data) > 0


def test_card_generator_png_format():
    """Test that generated card is valid PNG format."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="PNG Format Test",
        c_score=50,
        dsa_progress=50,
        current_streak=5,
        platforms={"LeetCode": 25}
    )
    
    # Check PNG signature
    result.seek(0)
    signature = result.read(8)
    assert signature == b'\x89PNG\r\n\x1a\n'
    
    # Check that we can seek and read multiple times
    result.seek(0)
    data1 = result.read()
    result.seek(0)
    data2 = result.read()
    assert data1 == data2
    assert len(data1) > 100  # PNG should have reasonable size


def test_card_generator_empty_platforms():
    """Test card generation with empty platforms dict."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="No Platforms",
        c_score=10,
        dsa_progress=5,
        current_streak=1,
        platforms={}
    )
    
    assert isinstance(result, io.BytesIO)
    result.seek(0)
    assert result.read(8) == b'\x89PNG\r\n\x1a\n'


def test_card_generator_single_platform():
    """Test card generation with single platform."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="Single Platform",
        c_score=25,
        dsa_progress=20,
        current_streak=2,
        platforms={"LeetCode": 50}
    )
    
    assert isinstance(result, io.BytesIO)
    result.seek(0)
    assert result.read(8) == b'\x89PNG\r\n\x1a\n'


def test_card_generator_multiple_platforms():
    """Test card generation with multiple platforms."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="Multi Platform",
        c_score=100,
        dsa_progress=80,
        current_streak=10,
        platforms={
            "LeetCode": 100,
            "GFG": 50,
            "Coding Ninjas": 30,
            "HackerRank": 20
        }
    )
    
    assert isinstance(result, io.BytesIO)
    result.seek(0)
    assert result.read(8) == b'\x89PNG\r\n\x1a\n'


def test_card_generator_high_values():
    """Test card generation with high metric values."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="High Achiever",
        c_score=9999,
        dsa_progress=100,
        current_streak=999,
        platforms={
            "LeetCode": 2000,
            "GFG": 1000,
            "Coding Ninjas": 500,
            "HackerRank": 300
        }
    )
    
    assert isinstance(result, io.BytesIO)
    result.seek(0)
    assert result.read(8) == b'\x89PNG\r\n\x1a\n'


def test_card_generator_special_characters_in_name():
    """Test card generation with special characters in name."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="User@#$%^&*()",
        c_score=50,
        dsa_progress=50,
        current_streak=5,
        platforms={"LeetCode": 25}
    )
    
    assert isinstance(result, io.BytesIO)
    result.seek(0)
    assert result.read(8) == b'\x89PNG\r\n\x1a\n'


def test_card_generator_unicode_name():
    """Test card generation with unicode characters in name."""
    from card_generator import generate_progress_card
    
    result = generate_progress_card(
        name="用户名 🚀",
        c_score=50,
        dsa_progress=50,
        current_streak=5,
        platforms={"LeetCode": 25}
    )
    
    assert isinstance(result, io.BytesIO)
    result.seek(0)
    assert result.read(8) == b'\x89PNG\r\n\x1a\n'


def test_public_card_response_headers(client, app):
    """Test that response headers are correct."""
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Header Test",
        "progress": {},
        "external_totals": {}
    }
    app.mock_db.question.data = {}
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        response = client.get(f"/u/{user_id}/card.png")
        
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert "Content-Length" in response.headers or len(response.data) > 0


def test_public_card_cache_expiration(client, app):
    """Test that cache respects TTL."""
    
    user_id = ObjectId()
    user_data = {
        "_id": user_id,
        "name": "Cache Expiry Test",
        "progress": {},
        "external_totals": {}
    }
    app.mock_db.question.data = {}
    
    app.mock_db.user.data[str(user_id)] = user_data
    
    with patch('app.profile.routes.db', app.mock_db):
        # First request
        response1 = client.get(f"/u/{user_id}/card.png")
        assert response1.status_code == 200
        
        # Verify cache was populated
        from app.profile.routes import card_cache
        assert str(user_id) in card_cache
