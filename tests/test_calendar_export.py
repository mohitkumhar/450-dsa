from datetime import date

from calendar_export import build_study_plan_ics


def test_build_study_plan_ics_exports_incomplete_topic_milestones():
    topics = [
        {
            "_id": "arrays",
            "name": "Arrays",
            "questions": [{"_id": "q1"}, {"_id": "q2"}],
        },
        {
            "_id": "trees",
            "name": "Trees",
            "questions": [{"_id": "q3"}],
        },
    ]
    progress = {"q1": {"done": True}, "q3": {"done": True}}

    calendar_text = build_study_plan_ics(topics, progress, start_date=date(2026, 5, 26))

    assert "BEGIN:VCALENDAR" in calendar_text
    assert "SUMMARY:Study milestone: Arrays" in calendar_text
    assert "DESCRIPTION:Complete remaining questions for Arrays. Progress: 1/2." in calendar_text
    assert "Study milestone: Trees" not in calendar_text
    assert "DTSTART;VALUE=DATE:20260526" in calendar_text
