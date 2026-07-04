from pathlib import Path


ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_env_example_documents_required_app_variables():
    contents = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "SECRET_KEY=replace-this-with-a-real-secret" in contents
    assert "MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/dsa_tracker" in contents
    assert "GITHUB_CLIENT_ID=your-github-client-id" in contents
    assert "GITHUB_CLIENT_SECRET=your-github-client-secret" in contents
    assert "GOOGLE_CLIENT_ID=your-google-client-id" in contents
    assert "GOOGLE_CLIENT_SECRET=your-google-client-secret" in contents
    assert "CLOUDINARY_CLOUD_NAME=your-cloud-name" in contents
    assert "CLOUDINARY_API_KEY=your-api-key" in contents
    assert "CLOUDINARY_API_SECRET=your-api-secret" in contents
    assert "RATELIMIT_STORAGE_URI=memory://" in contents
