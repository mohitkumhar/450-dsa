import requests
import json

r = requests.post("https://leetcode.com/graphql", json={
    "query": '{ userContestRanking(username: "mohitkumhar") { attendedContestsCount rating globalRanking topPercentage } }'
})
print(r.text)
