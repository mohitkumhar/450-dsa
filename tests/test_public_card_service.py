from io import BytesIO

from bson.objectid import ObjectId

from app.profile.card_service import get_public_card_image


class FakeCache(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def set(self, key, value, timeout=None):
        self[key] = value

    def delete(self, key):
        self.pop(key, None)


class FakeUserCollection:
    def __init__(self, user):
        self.user = user

    def find_one(self, query):
        if self.user and query.get("_id") == self.user["_id"]:
            return self.user
        return None


class FakeQuestionCollection:
    def __init__(self, questions):
        self.questions = list(questions)

    def count_documents(self, query):
        return len(self.questions)

    def find(self, *args, **kwargs):
        return list(self.questions)


class FakeDB:
    def __init__(self, user, questions):
        self.user = FakeUserCollection(user)
        self.question = FakeQuestionCollection(questions)


def test_get_public_card_image_builds_and_caches(monkeypatch):
    user_id = ObjectId()
    user = {
        "_id": user_id,
        "name": "Card User",
        "progress": {"q1": {"done": True}},
        "external_totals": {"LeetCode": 12},
    }
    fake_db = FakeDB(user, [{"_id": "q1", "url": "https://leetcode.com/problems/two-sum"}])
    fake_cache = FakeCache()
    generated = []

    def fake_generate(name, c_score, dsa_progress, current_streak, platforms):
        generated.append((name, c_score, dsa_progress, current_streak, platforms))
        return BytesIO(b"fake-png")

    monkeypatch.setattr("app.profile.card_service.db", fake_db)
    monkeypatch.setattr("app.profile.card_service.card_cache", fake_cache)
    monkeypatch.setattr("app.profile.card_service.compute_c_score", lambda user_doc: {"c_score": 144, "dsa_done": 1})
    monkeypatch.setattr("app.profile.card_service.compute_streak", lambda progress, **kw: (4, 8))
    monkeypatch.setattr("app.profile.card_service.compute_user_platforms", lambda solved, totals, all_questions: {"LeetCode": 12})
    monkeypatch.setattr("app.profile.card_service.card_generator.generate_progress_card", fake_generate)

    first, first_etag, first_last_modified = get_public_card_image(str(user_id), user_id)
    second, second_etag, second_last_modified = get_public_card_image(str(user_id), user_id)

    assert first.read() == b"fake-png"
    second.seek(0)
    assert second.read() == b"fake-png"
    assert len(generated) == 1
    assert generated[0] == ("Card User", 144, 100.0, 4, {"LeetCode": 12})
    assert first_etag == second_etag
    assert first_etag.startswith("progress-card-")
    assert first_last_modified == second_last_modified


def test_get_public_card_image_raises_for_missing_user(monkeypatch):
    fake_db = FakeDB(None, [])
    fake_cache = FakeCache()
    user_id = ObjectId()

    monkeypatch.setattr("app.profile.card_service.db", fake_db)
    monkeypatch.setattr("app.profile.card_service.card_cache", fake_cache)

    try:
        get_public_card_image(str(user_id), user_id)
    except LookupError as exc:
        assert "User not found" in str(exc)
    else:
        raise AssertionError("Expected LookupError for missing user")
