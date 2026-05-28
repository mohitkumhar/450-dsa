from datetime import timezone, timedelta
from app.utils import utc_now

# Spaced repetition intervals (in days) based on question difficulty
REVISION_INTERVALS = {
    "Easy": 30,
    "Medium": 14,
    "Hard": 7,
}


def get_next_recommendation(user, db, pre=None):
    """Calculate the recommended next problem for the user with a reason and message.

    Returns:
        dict: {
            "question": dict (containing details: _id, problem, topic, difficulty, url, url2),
            "reason": str ("Due Revision", "Needs Practice", "Goal Progress", "Next in Topic"),
            "message": str
        } or None if all questions are completed.
    """
    if not user or not user.is_authenticated:
        # Default to first question of the first topic for anonymous/guest users
        if pre and pre.get("topics") and pre.get("all_questions"):
            first_topic = pre["topics"][0]
            first_topic_questions = [
                q for q in pre["all_questions"] if q["topic"] == first_topic["_id"]
            ]
            if first_topic_questions:
                return {
                    "question": first_topic_questions[0],
                    "reason": "Next in Topic",
                    "message": f"Start your journey with the first question in {first_topic['name']}!"
                }
        return None

    progress = user.progress or {}

    # Extract topics and questions metadata
    if pre:
        topics = pre.get("topics", [])
        all_questions = pre.get("all_questions", [])
        topic_lookup = pre.get("topic_lookup", {})
    else:
        topics_cursor = db.topic.find().sort("position", 1)
        topics = [{"_id": str(t["_id"]), "name": t["name"], "position": t.get("position", 0)} for t in topics_cursor]
        questions_cursor = db.question.find()
        all_questions = [{
            "_id": str(q["_id"]),
            "topic": str(q["topic"]),
            "problem": q.get("problem", ""),
            "url": q.get("url", ""),
            "url2": q.get("url2", ""),
            "difficulty": q.get("difficulty", "Medium")
        } for q in questions_cursor]
        topic_lookup = {t["_id"]: {"name": t["name"], "position": t["position"]} for t in topics}

    if not all_questions:
        return None

    # Map questions for fast O(1) lookup
    questions_by_id = {q["_id"]: q for q in all_questions}
    questions_by_topic = {}
    for q in all_questions:
        questions_by_topic.setdefault(q["topic"], []).append(q)

    # 1. DUE REVISION (Spaced Repetition)
    now = utc_now()
    overdue_questions = []

    for q_id, prog in progress.items():
        if prog.get("done") and q_id in questions_by_id:
            q = questions_by_id[q_id]
            difficulty = q.get("difficulty", "Medium")
            interval_days = REVISION_INTERVALS.get(difficulty, 14)

            timestamp = prog.get("timestamp")
            if not timestamp:
                continue

            # Ensure timezone compatibility
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            due_date = timestamp + timedelta(days=interval_days)
            if now > due_date:
                overdue_duration = now - due_date
                overdue_questions.append((q, overdue_duration))

    if overdue_questions:
        # Pick the most overdue question
        overdue_questions.sort(key=lambda x: x[1], reverse=True)
        recommended_q = overdue_questions[0][0]
        topic_name = topic_lookup.get(recommended_q["topic"], {}).get("name", "DSA")
        return {
            "question": recommended_q,
            "reason": "Due Revision",
            "message": f"You completed this {recommended_q['difficulty']} question in {topic_name} some time ago. It's time to revise!"
        }

    # 2. WEAK TAG / NEEDS PRACTICE (Skipped questions)
    skipped_questions = []
    for q_id, prog in progress.items():
        if prog.get("skipped") and not prog.get("done") and q_id in questions_by_id:
            skipped_questions.append(questions_by_id[q_id])

    if skipped_questions:
        topic_positions = {t["_id"]: t["position"] for t in topics}

        def get_seq_order(q):
            t_pos = topic_positions.get(q["topic"], 999)
            topic_qs = questions_by_topic.get(q["topic"], [])
            try:
                q_idx = topic_qs.index(q)
            except ValueError:
                q_idx = 999
            return (t_pos, q_idx)

        skipped_questions.sort(key=get_seq_order)
        recommended_q = skipped_questions[0]
        topic_name = topic_lookup.get(recommended_q["topic"], {}).get("name", "DSA")
        return {
            "question": recommended_q,
            "reason": "Needs Practice",
            "message": f"You skipped this question in {topic_name} earlier. Try tackling it now to strengthen your weak areas!"
        }

    # Calculate completion ratios
    topic_completion = {}
    for topic in topics:
        t_id = topic["_id"]
        t_qs = questions_by_topic.get(t_id, [])
        if not t_qs:
            topic_completion[t_id] = 0.0
            continue
        done_count = sum(1 for q in t_qs if progress.get(q["_id"], {}).get("done"))
        topic_completion[t_id] = done_count / len(t_qs)

    # 3. GOAL PROGRESS (Nearly completed topics)
    near_completed_topics = []
    for t_id, pct in topic_completion.items():
        if 0.7 <= pct < 1.0:
            near_completed_topics.append((t_id, pct))

    if near_completed_topics:
        near_completed_topics.sort(key=lambda x: x[1], reverse=True)
        for t_id, pct in near_completed_topics:
            t_qs = questions_by_topic.get(t_id, [])
            for q in t_qs:
                if not progress.get(q["_id"], {}).get("done"):
                    topic_name = topic_lookup.get(t_id, {}).get("name", "DSA")
                    return {
                        "question": q,
                        "reason": "Goal Progress",
                        "message": f"You have completed {int(pct * 100)}% of the {topic_name} topic! Solve this to get closer to 100%."
                    }

    # 4. NEXT IN TOPIC (In-progress or unstarted)
    # 4.1 In-progress topics
    for topic in topics:
        t_id = topic["_id"]
        pct = topic_completion.get(t_id, 0.0)
        if 0.0 < pct < 1.0:
            t_qs = questions_by_topic.get(t_id, [])
            for q in t_qs:
                if not progress.get(q["_id"], {}).get("done"):
                    return {
                        "question": q,
                        "reason": "Next in Topic",
                        "message": f"Continue your progress in {topic['name']} with the next unsolved question."
                    }

    # 4.2 Unstarted topics
    for topic in topics:
        t_id = topic["_id"]
        pct = topic_completion.get(t_id, 0.0)
        t_qs = questions_by_topic.get(t_id, [])
        if pct == 0.0 and t_qs:
            return {
                "question": t_qs[0],
                "reason": "Next in Topic",
                "message": f"Start learning the {topic['name']} topic with this question!"
            }

    # If all questions across all topics are completed
    return None
