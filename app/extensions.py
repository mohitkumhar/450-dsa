from authlib.integrations.flask_client import OAuth
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_pymongo import PyMongo
from werkzeug.local import LocalProxy
from flask_caching import Cache

mongo = PyMongo()
db = LocalProxy(lambda: mongo.db)
bcrypt = Bcrypt()
login_manager = LoginManager()
oauth = OAuth()
limiter = Limiter(key_func=get_remote_address, default_limits=[], headers_enabled=True)
github = LocalProxy(lambda: oauth.create_client("github"))
google = LocalProxy(lambda: oauth.create_client("google"))
cache = Cache()


# GSSoC Redis Connection Failure Recovery
# Fallback to local thread-safe memory storage on connection timeout.
