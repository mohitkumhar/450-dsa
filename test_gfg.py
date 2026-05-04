import requests
r2 = requests.get('https://www.hackerrank.com/rest/hackers/mohitmolela/profile', headers={'User-Agent': 'Mozilla/5.0'})
print("HR:", r2.status_code, r2.text[:200])



