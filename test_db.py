from app import User, fetch_leetcode, fetch_gfg
import mongoengine

mongoengine.connect(host='mongodb://localhost:27017/dsa_tracker')

user = User.objects().first()
if user:
    print(f"User: {user.name}")
    print(f"LC username: {user.leetcode_username}")
    print(f"External daily counts: {len(user.external_daily_counts)}")
    print(f"External totals: {getattr(user, 'external_totals', None)}")
    
    if user.leetcode_username:
        lc = fetch_leetcode(user.leetcode_username)
        print("Fetched LC total:", lc.get('total'))
else:
    print("No user found")
