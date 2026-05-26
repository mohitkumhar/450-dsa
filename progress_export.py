import csv
from io import StringIO


CSV_HEADERS = ['Topic', 'Problem', 'Done', 'Bookmarked', 'Notes', 'Difficulty', 'URL', 'URL2']
CSV_FORMULA_PREFIXES = ('=', '+', '-', '@')


def escape_csv_formula_cell(value):
    if not isinstance(value, str) or value == '':
        return value
    if value.startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def build_progress_csv(questions, topic_lookup, progress):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)

    for question in questions:
        question_id = str(question.get('_id'))
        item_progress = progress.get(question_id, {}) or {}
        topic_name = topic_lookup.get(question.get('topic'), 'Unknown')
        writer.writerow([
            topic_name,
            question.get('problem', ''),
            bool(item_progress.get('done', False)),
            bool(item_progress.get('bookmark', False)),
            escape_csv_formula_cell(item_progress.get('notes', '')),
            question.get('difficulty', 'Medium'),
            question.get('url', ''),
            question.get('url2', ''),
        ])

    return output.getvalue()
