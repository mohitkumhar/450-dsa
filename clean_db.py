import pymongo

c = pymongo.MongoClient('mongodb://localhost:27017/')
db = c['dsa_tracker']

res = db.user.update_many({}, {
    '$unset': {
        'github_merged_prs': '', 
        'github_prs': '', 
        'github_issues': '', 
        'github_commits': ''
    }
})

print(res.modified_count)
