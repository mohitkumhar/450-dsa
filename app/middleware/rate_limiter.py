import time
from flask import request, jsonify

ip_request_counts = {}
WINDOW_SECONDS = 60
MAX_REQUESTS = 100

def rate_limiter_middleware():
    ip = request.remote_addr or "unknown"
    now = time.time()
    record = ip_request_counts.get(ip)

    if not record or now > record["reset_time"]:
        ip_request_counts[ip] = {"count": 1, "reset_time": now + WINDOW_SECONDS}
        return

    if record["count"] >= MAX_REQUESTS:
        return jsonify({"error": "Too many requests. Please try again later."}), 429

    record["count"] += 1
