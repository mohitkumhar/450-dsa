import re


def build_topic_notes_markdown(topic_name, questions, progress):
    lines = [f'# {topic_name} Notes']

    for question in questions:
        question_id = str(question.get('_id'))
        note = (progress.get(question_id, {}) or {}).get('notes', '').strip()
        if not note:
            continue

        problem = question.get('problem') or 'Untitled Problem'
        lines.extend(['', f'## {problem}', '', note])

    return '\n'.join(lines) + '\n'


def topic_notes_filename(topic_name):
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic_name).strip('_').lower()
    return f'{slug or "topic"}_notes.md'


def build_all_notes_markdown(topics, questions_by_topic, progress):
    """Build a single Markdown document with all non-empty notes
    grouped by topic and question.

    Args:
        topics: List of topic dicts with '_id' and 'name' keys,
                ordered by position.
        questions_by_topic: Dict mapping topic_id (str) to list
                            of question dicts (each with '_id', 'problem').
        progress: User progress dict mapping question_id to
                  {'notes': str, ...}.

    Returns:
        str: Complete Markdown document. Returns a placeholder
             message when no notes exist.
    """
    sections = []
    for topic in topics:
        topic_id = str(topic['_id'])
        questions = questions_by_topic.get(topic_id, [])
        topic_md = build_topic_notes_markdown(
            topic['name'], questions, progress,
        )
        # Include only topics with at least one note
        # (more than just the header line)
        if len(topic_md.strip().split('\n')) > 1:
            sections.append(topic_md)

    if not sections:
        return '# All Notes\n\n_No notes found._\n'

    return '\n'.join(sections) + '\n'
