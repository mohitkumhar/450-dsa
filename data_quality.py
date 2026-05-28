import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


DATA_PATH = Path(__file__).resolve().with_name("data.json")

# These are intentional cross-topic references in the Love Babbar sheet.
ALLOWED_DUPLICATE_PROBLEMS = {
    "chocolate distribution problem",
    "word wrap problem",
    "edit distance",
    "word break problem",
    "count all palindromic subsequence in a given string",
    "rearrange characters in a string such that no two adjacent are same",
    "given a sequence of words print all anagrams together",
    "subset sum problem",
}

ALLOWED_DUPLICATE_URLS = {
    "https://practice.geeksforgeeks.org/problems/kadanes-algorithm/0",
    "https://practice.geeksforgeeks.org/problems/minimum-number-of-jumps/0",
    "https://practice.geeksforgeeks.org/problems/inversion-of-array/0",
    "https://practice.geeksforgeeks.org/problems/chocolate-distribution-problem/0",
    "https://practice.geeksforgeeks.org/problems/longest-repeating-subsequence/0",
    "https://practice.geeksforgeeks.org/problems/permutations-of-a-given-string/0",
    "https://practice.geeksforgeeks.org/problems/word-wrap/0",
    "https://practice.geeksforgeeks.org/problems/edit-distance3702/1",
    "https://practice.geeksforgeeks.org/problems/parenthesis-checker/0",
    "https://practice.geeksforgeeks.org/problems/word-break/0",
    "https://practice.geeksforgeeks.org/problems/count-palindromic-subsequences/1",
    "https://practice.geeksforgeeks.org/problems/longest-common-subsequence/0",
    "https://practice.geeksforgeeks.org/problems/rearrange-characters4649/1",
    "https://practice.geeksforgeeks.org/problems/k-anagrams-1/0",
    "https://practice.geeksforgeeks.org/problems/allocate-minimum-number-of-pages/0",
    "https://practice.geeksforgeeks.org/problems/merge-k-sorted-linked-lists/1",
    "https://practice.geeksforgeeks.org/problems/first-non-repeating-character-in-a-stream/0",
    "https://www.geeksforgeeks.org/minimize-cash-flow-among-given-set-friends-borrowed-money",
    "https://practice.geeksforgeeks.org/problems/minimum-cost-of-ropes/0",
    "https://practice.geeksforgeeks.org/problems/rat-in-a-maze-problem/1",
    "https://practice.geeksforgeeks.org/problems/m-coloring-problem/0",
    "https://practice.geeksforgeeks.org/problems/subset-sum-problem2014/1",
    "https://www.geeksforgeeks.org/find-if-there-is-a-path-of-more-than-k-length-from-a-source",
}

ALLOWED_DUPLICATE_URL2S = {
    "https://www.codingninjas.com/codestudio/problems/create-a-graph-and-print-it_1214551",
}


def load_data(path=DATA_PATH):
    with open(path, encoding="utf-8") as data_file:
        return json.load(data_file)


def normalize_problem(value):
    value = (value or "").strip().lower()
    value = re.sub(r"\[[^\]]*\]", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(value):
    value = (value or "").strip()
    if not value:
        return ""

    parts = urlsplit(value)
    path = re.sub(r"/+$", "", parts.path)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def iter_questions(data):
    for topic in data:
        topic_name = topic.get("topicName", "")
        for index, question in enumerate(topic.get("questions", [])):
            yield {
                "topic": topic_name,
                "index": index,
                "problem": question.get("Problem", ""),
                "url": question.get("URL", ""),
                "url2": question.get("URL2", ""),
            }


def duplicate_groups(data, field, normalizer):
    groups = defaultdict(list)
    for question in iter_questions(data):
        key = normalizer(question[field])
        if key:
            groups[key].append(question)

    return {key: values for key, values in groups.items() if len(values) > 1}


def unexpected_duplicate_groups(data):
    problem_duplicates = duplicate_groups(data, "problem", normalize_problem)
    url_duplicates = duplicate_groups(data, "url", normalize_url)
    url2_duplicates = duplicate_groups(data, "url2", normalize_url)

    return {
        "problems": {
            key: values
            for key, values in problem_duplicates.items()
            if key not in ALLOWED_DUPLICATE_PROBLEMS
        },
        "urls": {
            key: values
            for key, values in url_duplicates.items()
            if key not in ALLOWED_DUPLICATE_URLS
        },
        "url2s": {
            key: values
            for key, values in url2_duplicates.items()
            if key not in ALLOWED_DUPLICATE_URL2S
        },
    }


def main():
    unexpected = unexpected_duplicate_groups(load_data())
    unexpected = {name: groups for name, groups in unexpected.items() if groups}

    if not unexpected:
        print("No unexpected duplicate problems or URLs found.")
        return 0

    for group_name, groups in unexpected.items():
        print(f"{group_name}:")
        for key, questions in groups.items():
            locations = ", ".join(f"{item['topic']}[{item['index']}]" for item in questions)
            print(f"  {key}: {locations}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
