from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/dsa_tracker')
db = client.get_default_database()

user = db.user.find_one()
if user:
    print(f"User: {user.get('name')}")
    print(f"LC username: {user.get('leetcode_username')}")
    print(f"External daily counts: {len(user.get('external_daily_counts', {}))}")
    print(f"External totals: {user.get('external_totals')}")
else:
    print("No user found")
