import os
import mongomock

# 1. Create in-memory mock MongoDB database
mock_db = mongomock.MongoClient().db

# 2. Patch app.extensions.db to use our mock database
import app.extensions
app.extensions.db = mock_db
app.extensions.mongo.db = mock_db

# 3. Bypass PyMongo real server connection initialization
from flask_pymongo import PyMongo
PyMongo.init_app = lambda self, app, *args, **kwargs: None

# 4. Create and start the Flask application
from app import create_app
app = create_app()

if __name__ == "__main__":
    print("--------------------------------------------------")
    print("Starting Flask server with in-memory Mock MongoDB.")
    print("Access the app at: http://127.0.0.1:5000")
    print("Note: Progress will reset when you stop the server.")
    print("--------------------------------------------------")
    app.run(debug=True, port=5000)
