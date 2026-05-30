from datetime import date, timedelta


def _ics_escape(value):
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_study_plan_ics(topics, progress, start_date=None, cadence_days=7):
    """Build an iCalendar file with upcoming topic study milestones."""
    start_date = start_date or date.today()
    progress = progress or {}
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//450 DSA Tracker//Study Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    milestone_index = 0
    for topic in topics:
        questions = topic.get("questions", [])
        if not questions:
            continue
        total = len(questions)
        done = sum(
            1
            for question in questions
            if progress.get(str(question.get("_id")), {}).get("done")
        )
        if done >= total:
            continue

        due_date = start_date + timedelta(days=milestone_index * cadence_days)
        end_date = due_date + timedelta(days=1)
        topic_id = str(topic.get("_id") or topic.get("name") or milestone_index)
        name = topic.get("name", "Study topic")
        summary = f"Study milestone: {name}"
        description = f"Complete remaining questions for {name}. Progress: {done}/{total}."

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:450-dsa-{_ics_escape(topic_id)}@450-dsa-tracker",
                f"DTSTAMP:{start_date.strftime('%Y%m%d')}T000000Z",
                f"DTSTART;VALUE=DATE:{due_date.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end_date.strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(description)}",
                "END:VEVENT",
            ]
        )
        milestone_index += 1

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
