import csv
from io import StringIO


CSV_HEADERS = ['Topic', 'Problem', 'Done', 'Bookmarked', 'Notes', 'Difficulty', 'URL', 'URL2']


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
            item_progress.get('notes', ''),
            question.get('difficulty', 'Medium'),
            question.get('url', ''),
            question.get('url2', ''),
        ])

    return output.getvalue()
