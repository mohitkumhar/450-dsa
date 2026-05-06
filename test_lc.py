import requests

def fetch_leetcode(username):
    try:
        r = requests.post("https://leetcode.com/graphql", json={
            "query": f'{{ matchedUser(username: "{username}") {{ submitStats: submitStatsGlobal {{ acSubmissionNum {{ difficulty count }} }} userCalendar {{ submissionCalendar }} }} }}'
        }, timeout=5)
        print(r.text)
    except Exception as e:
        print(e)

fetch_leetcode("mohitkumhar")
