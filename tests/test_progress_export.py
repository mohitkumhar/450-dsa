import csv
from io import StringIO

from progress_export import CSV_HEADERS, build_progress_csv


def parse_csv(value):
    return list(csv.reader(StringIO(value)))


def test_progress_csv_includes_all_questions_with_statuses():
    questions = [
        {'_id': 'q1', 'topic': 't1', 'problem': 'Two Sum', 'url': 'https://example.com/two-sum'},
        {'_id': 'q2', 'topic': 't2', 'problem': 'Binary Search'},
    ]
    progress = {
        'q1': {'done': True, 'bookmark': True, 'notes': 'Use a hash map.'},
    }

    rows = parse_csv(build_progress_csv(questions, {'t1': 'Arrays', 't2': 'Search'}, progress))

    assert rows[0] == CSV_HEADERS
    assert rows[1] == ['Arrays', 'Two Sum', 'True', 'True', 'Use a hash map.','Medium', 'https://example.com/two-sum','']
    assert rows[2] == ['Search', 'Binary Search', 'False', 'False','','Medium', '', '']


def test_progress_csv_escapes_commas_and_newlines_in_notes():
    questions = [{'_id': 'q1', 'topic': 't1', 'problem': 'Intervals'}]
    progress = {'q1': {'notes': 'sort by start,\nthen merge'}}

    rows = parse_csv(build_progress_csv(questions, {'t1': 'Arrays'}, progress))

    assert rows[1][4] == 'sort by start,\nthen merge'


def test_progress_csv_uses_unknown_topic_fallback():
    questions = [{'_id': 'q1', 'topic': 'missing', 'problem': 'Mystery'}]

    rows = parse_csv(build_progress_csv(questions, {}, {}))

    assert rows[1][0] == 'Unknown'
