import json
import re
from datetime import datetime

import requests

from app.utils import normalize_coding_ninjas_profile_id


LEETCODE_PROFILE_QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
    userCalendar {
      submissionCalendar
    }
  }
  userContestRanking(username: $username) {
    attendedContestsCount
    rating
    globalRanking
    topPercentage
  }
}
"""


def build_leetcode_profile_payload(username):
    return {
        "query": LEETCODE_PROFILE_QUERY,
        "variables": {"username": username},
    }


def fetch_leetcode(username):
    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json=build_leetcode_profile_payload(username),
            timeout=8,
        )
        response_json = response.json().get("data", {})
        data = response_json.get("matchedUser", {})
        if not data:
            return {}
        calendar_str = data.get("userCalendar", {}).get("submissionCalendar", "{}")
        calendar_data = json.loads(calendar_str) if calendar_str else {}
        result_calendar = {}
        for ts, count in calendar_data.items():
            day = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
            result_calendar[day] = result_calendar.get(day, 0) + count
        total_solved = 0
        diff_stats = {"Easy": 0, "Medium": 0, "Hard": 0}
        stats = data.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        for stat in stats:
            difficulty = stat.get("difficulty")
            if difficulty == "All":
                total_solved = stat.get("count", 0)
            elif difficulty in diff_stats:
                diff_stats[difficulty] = stat.get("count", 0)
        contest = response_json.get("userContestRanking", {})
        return {
            "calendar": result_calendar,
            "total": total_solved,
            "difficulty": diff_stats,
            "contest": contest,
        }
    except Exception as exc:
        print("LC Error", exc)
        return {}


def fetch_leetcode_rating_history(username):
    """Fetch contest rating history for the rating graph."""
    try:
        query = """
        query userContestRankingInfo($username: String!) {
          userContestRankingHistory(username: $username) {
            attended
            rating
            contest { title startTime }
          }
        }"""
        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            timeout=10,
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
        )
        history_raw = response.json().get("data", {}).get("userContestRankingHistory", [])
        result = []
        for item in history_raw:
            if item.get("attended"):
                ts = item.get("contest", {}).get("startTime", 0)
                day = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
                result.append({"x": day, "y": round(float(item.get("rating", 0)), 0)})
        return sorted(result, key=lambda item: item["x"])
    except Exception as exc:
        print("LC Rating History Error", exc)
        return []


def fetch_lc_badges(username):
    """Fetch LeetCode badges/awards for the user."""
    try:
        query = """
        query userBadges($username: String!) {
          matchedUser(username: $username) {
            badges { id displayName icon }
            upcomingBadges { name icon }
          }
        }"""
        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            timeout=8,
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
        )
        badges_raw = response.json().get("data", {}).get("matchedUser", {}).get("badges", [])
        return [
            {
                "name": badge["displayName"],
                "icon": "https://leetcode.com" + badge["icon"]
                if badge.get("icon", "").startswith("/")
                else badge.get("icon", ""),
            }
            for badge in badges_raw
        ]
    except Exception as exc:
        print("LC Badges Error", exc)
        return []


def fetch_hr_badges(username):
    """Fetch HackerRank badges and total solved count."""
    try:
        response = requests.get(
            f"https://www.hackerrank.com/rest/hackers/{username}/badges",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if response.status_code == 200:
            data = response.json().get("models", [])
            badges = [
                {"name": badge.get("badge_name", ""), "stars": min(int(badge.get("stars", 0)), 5)}
                for badge in data
                if badge.get("badge_name") and int(badge.get("stars", 0)) > 0
            ]
            total_solved = sum(badge.get("solved", 0) for badge in data)
            return badges, total_solved
        return [], 0
    except Exception as exc:
        print("HR Badges Error", exc)
        return [], 0


def fetch_github(username):
    try:
        response = requests.get(f"https://github.com/users/{username}/contributions", timeout=5)
        matches = re.findall(r"(\d+|No)\s+contributions?\s+on\s+(\d{4}-\d{2}-\d{2})", response.text)
        result_calendar = {}
        for count_str, date_str in matches:
            count = 0 if count_str == "No" else int(count_str)
            result_calendar[date_str] = count

        response_issues = requests.get(
            f"https://api.github.com/search/issues?q=type:issue+author:{username}",
            timeout=5,
        ).json()
        response_prs = requests.get(
            f"https://api.github.com/search/issues?q=type:pr+author:{username}",
            timeout=5,
        ).json()
        response_merged = requests.get(
            f"https://api.github.com/search/issues?q=type:pr+is:merged+author:{username}",
            timeout=5,
        ).json()
        headers = {"Accept": "application/vnd.github.cloak-preview+json"}
        response_commits = requests.get(
            f"https://api.github.com/search/commits?q=author:{username}",
            headers=headers,
            timeout=5,
        ).json()

        stats = {
            "issues": response_issues.get("total_count", 0),
            "prs": response_prs.get("total_count", 0),
            "merged_prs": response_merged.get("total_count", 0),
            "commits": response_commits.get("total_count", 0),
        }

        return {"calendar": result_calendar, "stats": stats}
    except Exception as exc:
        print("GH Error", exc)
        return {}


def fetch_gfg(username):
    """Fetch GFG solved count via multiple fallback methods."""
    try:
        try:
            response = requests.get(
                f"https://geeks-for-geeks-stats-api.vercel.app/?raw=Y&userName={username}",
                timeout=6,
            )
            if response.status_code == 200:
                data = response.json()
                total = data.get("totalProblemsSolved") or data.get("total_problems_solved", 0)
                if total and int(total) > 0:
                    return {"total": int(total)}
        except Exception as exc:
            print("GFG Error", exc)

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(
                f"https://practiceapi.geeksforgeeks.org/api/v1/user/practice/stats/?user={username}",
                headers=headers,
                timeout=6,
            )
            if response.status_code == 200:
                data = response.json()
                total = data.get("data", {}).get("total_problems_solved", 0)
                if total:
                    return {"total": int(total)}
        except Exception as exc:
            print("GFG Error", exc)

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}
        response = requests.get(f"https://www.geeksforgeeks.org/user/{username}/", timeout=8, headers=headers)
        for pattern in [
            r'"total_problems_solved"\s*[:=]\s*(\d+)',
            r'"totalProblemsSolved"\s*[:=]\s*(\d+)',
            r"total_problems_solved.*?(\d+)",
            r"Problems Solved[^\d]*(\d+)",
            r'class="score_card_value"[^>]*>(\d+)<',
        ]:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                return {"total": int(match.group(1))}
        return {"total": 0}
    except Exception as exc:
        print("GFG Error", exc)
        return {}


def fetch_atcoder(handle):
    try:
        r = requests.get(
            'https://kenkoooo.com/atcoder/atcoder-api/v3/user/acceptance_count',
            params={'user': handle}, timeout=8)
        if r.status_code == 200:
            return {'total': r.json().get('count', 0)}
    except Exception as e:
        print(f'AtCoder Error: {e}')
    return {}


def fetch_coding_ninjas(username):
    """Fetch Coding Ninjas/Code360 solved count from public profile pages."""
    profile_id = normalize_coding_ninjas_profile_id(username)
    if not profile_id:
        return {}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
        "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        api_url = "https://www.naukri.com/code360/api/v3/public_section/profile/user_details"
        response = requests.get(api_url, params={"uuid": profile_id}, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json().get("data") or {}
            total = 0
            for domain_key in ("dsa_domain_data", "web_domain_data", "analytics_domain_data"):
                count_data = data.get(domain_key, {}).get("problem_count_data", {})
                total += int(count_data.get("total_count") or 0)
            if total > 0:
                return {"total": total}
    except Exception as exc:
        print("Coding Ninjas API Error", exc)

    urls = [
        f"https://www.naukri.com/code360/profile/{profile_id}",
        f"https://www.codingninjas.com/studio/profile/{profile_id}",
        f"https://www.codingninjas.com/codestudio/profile/{profile_id}",
    ]
    patterns = [
        r'"totalProblemsSolved"\s*:\s*(\d+)',
        r'"total_problems_solved"\s*:\s*(\d+)',
        r'"problemsSolved"\s*:\s*(\d+)',
        r'"solvedProblems"\s*:\s*(\d+)',
        r"Problems\s+Solved[^\d]{0,80}(\d+)",
        r"Solved\s+Problems[^\d]{0,80}(\d+)",
        r"(\d+)[^\d]{0,80}Problems\s+Solved",
    ]

    try:
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=8)
                if response.status_code != 200:
                    continue
                for pattern in patterns:
                    match = re.search(pattern, response.text, re.IGNORECASE)
                    if match:
                        return {"total": int(match.group(1))}
            except Exception as exc:
                print("Coding Ninjas Error", exc)
        return {"total": 0}
    except Exception as exc:
        print("Coding Ninjas Error", exc)
        return {}
