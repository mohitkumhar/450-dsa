from notes_export import build_all_notes_markdown, build_topic_notes_markdown, topic_notes_filename


def test_topic_notes_markdown_includes_only_questions_with_notes():
    questions = [
        {'_id': 'q1', 'problem': 'Two Sum'},
        {'_id': 'q2', 'problem': 'Missing Number'},
        {'_id': 'q3', 'problem': 'Kadane Algorithm'},
    ]
    progress = {
        'q1': {'notes': 'Use a hash map.'},
        'q2': {'notes': '   '},
        'q3': {'done': True},
    }

    markdown = build_topic_notes_markdown('Arrays', questions, progress)

    assert markdown == '# Arrays Notes\n\n## Two Sum\n\nUse a hash map.\n'
    assert 'Missing Number' not in markdown
    assert 'Kadane Algorithm' not in markdown


def test_topic_notes_markdown_falls_back_for_untitled_problem():
    markdown = build_topic_notes_markdown('Graphs', [{'_id': 'q1'}], {'q1': {'notes': 'BFS first.'}})

    assert '## Untitled Problem' in markdown
    assert 'BFS first.' in markdown


def test_topic_notes_filename_sanitizes_topic_name():
    assert topic_notes_filename('Dynamic Programming & Greedy!') == 'dynamic_programming_greedy_notes.md'
    assert topic_notes_filename('***') == 'topic_notes.md'


def test_all_notes_markdown_groups_notes_by_topic():
    topics = [
        {'_id': 't1', 'name': 'Arrays'},
        {'_id': 't2', 'name': 'Strings'},
    ]
    questions_by_topic = {
        't1': [
            {'_id': 'q1', 'problem': 'Two Sum'},
            {'_id': 'q2', 'problem': 'Missing Number'},
        ],
        't2': [
            {'_id': 'q3', 'problem': 'Reverse String'},
        ],
    }
    progress = {
        'q1': {'notes': 'Use a hash map.'},
        'q3': {'notes': 'Two pointers.'},
    }

    markdown = build_all_notes_markdown(topics, questions_by_topic, progress)

    assert '# Arrays Notes' in markdown
    assert '# Strings Notes' in markdown
    assert '## Two Sum' in markdown
    assert 'Use a hash map.' in markdown
    assert '## Reverse String' in markdown
    assert 'Two pointers.' in markdown
    # Topics without notes and questions without notes are excluded
    assert 'Missing Number' not in markdown


def test_all_notes_markdown_excludes_topic_with_no_notes():
    topics = [
        {'_id': 't1', 'name': 'Arrays'},
        {'_id': 't2', 'name': 'Strings'},
    ]
    questions_by_topic = {
        't1': [{'_id': 'q1', 'problem': 'Two Sum'}],
        't2': [{'_id': 'q2', 'problem': 'Reverse String'}],
    }
    # Only Arrays has notes
    progress = {'q1': {'notes': 'Use a hash map.'}}

    markdown = build_all_notes_markdown(topics, questions_by_topic, progress)

    assert '# Arrays Notes' in markdown
    assert '## Two Sum' in markdown
    assert 'Use a hash map.' in markdown
    # Strings topic has no notes — its header must not appear
    assert '# Strings Notes' not in markdown


def test_all_notes_markdown_returns_placeholder_when_no_notes():
    topics = [{'_id': 't1', 'name': 'Arrays'}]
    questions_by_topic = {'t1': [{'_id': 'q1', 'problem': 'Two Sum'}]}
    progress = {'q1': {'done': True}}  # No notes

    markdown = build_all_notes_markdown(topics, questions_by_topic, progress)

    assert '_No notes found._' in markdown


def test_all_notes_markdown_preserves_topic_order():
    topics = [
        {'_id': 't3', 'name': 'Linked List'},
        {'_id': 't1', 'name': 'Arrays'},
        {'_id': 't2', 'name': 'Strings'},
    ]
    questions_by_topic = {
        't1': [{'_id': 'q1', 'problem': 'Two Sum'}],
        't2': [{'_id': 'q2', 'problem': 'Reverse String'}],
        't3': [{'_id': 'q3', 'problem': 'Detect Cycle'}],
    }
    progress = {
        'q1': {'notes': 'Hash map.'},
        'q2': {'notes': 'Two pointers.'},
        'q3': {'notes': 'Floyd.'},
    }

    markdown = build_all_notes_markdown(topics, questions_by_topic, progress)

    # Topics appear in the order given
    arrays_pos = markdown.index('# Arrays Notes')
    strings_pos = markdown.index('# Strings Notes')
    linkedlist_pos = markdown.index('# Linked List Notes')
    assert linkedlist_pos < arrays_pos < strings_pos


def test_all_notes_markdown_empty_topic_list():
    """An empty topic list should produce the placeholder message."""
    markdown = build_all_notes_markdown([], {}, {})
    assert '_No notes found._' in markdown
