from app.auth.routes import UserWrapper


def test_user_wrapper_treats_null_progress_as_empty_dict():
    user = UserWrapper({"_id": "user-1", "progress": None})

    assert user.progress == {}


def test_user_wrapper_preserves_existing_progress_dict():
    progress = {"question-1": {"done": True}}
    user = UserWrapper({"_id": "user-1", "progress": progress})

    assert user.progress == progress
