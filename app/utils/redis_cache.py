import os
import json
import redis

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

def get_cache(key: str):
    try:
        data = redis_client.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        print(f"Redis cache get failure, falling back to database: {e}")
        return None

def set_cache(key: str, value, ttl: int = 3600):
    try:
        redis_client.setex(key, ttl, json.dumps(value))
    except Exception as e:
        print(f"Redis cache set failure: {e}")
