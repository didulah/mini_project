"""
insert_timetable.py
--------------------
Subjects සහ Timetable entries manually insert කරන්න use කරන repo-root script එකක්.

මේ script එක SAFE ලෙස re-run කරන්න පුළුවන් (idempotent):
    - subject_code එකක් දැනටමත් DB එකේ තියෙනවා නම් - ඒක SKIP කරනවා (duplicate හදන්නෙ නෑ)
    - timetable row එකක් (same subject + lecturer + day + start_time) දැනටමත් තියෙනවා නම් - SKIP කරනවා
    - අලුත් row එකක් නම් විතරක් INSERT කරනවා
    - අවසානයේදී sync_all_enrollments() call වෙනවා - ඒකෙන් අලුතෙන් add උනු
      subject එකකට, දැනටමත් ඉන්න සියලුම students ලා auto-enroll වෙනවා
      (subject select කරන්න ඕන නෑ - හැම student කෙනෙක්ම හැම subject එකක්ම
      හදාරනවා කියන model එකට අනුව)

භාවිතය:
    1. පහළ SUBJECTS සහ TIMETABLE list දෙක ඔයාගේ actual data එකට ගැලපෙන්න edit කරන්න
    2. lecturer username එක Admin Panel එකෙන් දැනටමත් හදලා තියෙන්න ඕන (script එක
       lecturer හෝ student හෝ අලුතින් හදන්නෙ නෑ - Admin Panel එකෙන්මයි ඒවා කරන්නෙ)
    3. Terminal එකේ:  python insert_timetable.py
"""

from datetime import datetime

from app import create_app
from extensions import db
from models import Subject, Lecturer, Timetable, sync_all_enrollments


# ---------------------------------------------------------------------------
# 1) SUBJECTS - මෙහි ඔයාගේ actual subjects ටික දාන්න
#    subject_code : unique code එකක් (ex: "CS101")
#    subject_name : full name එක
# ---------------------------------------------------------------------------
SUBJECTS = [
    {"subject_code": "ET001", "subject_name": "Engineering Maths"},
    {"subject_code": "ET002", "subject_name": "Computer Programming"},
    {"subject_code": "ET003", "subject_name": "Electrical Circuits"},
    {"subject_code": "ET004", "subject_name": "Physics"},
    # ... ඔයාගේ subjects මෙතනට add කරන්න
]


# ---------------------------------------------------------------------------
# 2) TIMETABLE - lecture slots ටික මෙහි දාන්න
#    subject_code    : ඉහත SUBJECTS list එකේ තියෙන code එකක් වෙන්න ඕන
#    lecturer_username: Admin Panel එකෙන් දැනටමත් හදපු lecturer ගේ username එක
#    day_of_week      : "Monday" | "Tuesday" | "Wednesday" | "Thursday" |
#                        "Friday" | "Saturday" | "Sunday"  (exact spelling, capital මුල් අකුරෙන්)
#    start_time / end_time : "HH:MM" format, 24-hour (ex: "09:00", "14:30")
# ---------------------------------------------------------------------------
TIMETABLE = [
    {
        "subject_code": "ET001",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Monday",
        "start_time": "09:00",
        "end_time": "12:00",
    },
    {
        "subject_code": "ET002",
        "lecturer_username": "Kalana",
        "day_of_week": "Monday",
        "start_time": "13:00",
        "end_time": "15:00",
    },
    {
        "subject_code": "ET002",
        "lecturer_username": "Kalana",
        "day_of_week": "Tuesday",
        "start_time": "09:00",
        "end_time": "12:00",
    },
    {
        "subject_code": "ET003",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Tuesday",
        "start_time": "13:00",
        "end_time": "15:00",
    },{
        "subject_code": "ET001",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Wednesday",
        "start_time": "09:00",
        "end_time": "12:00",
    },
    {
        "subject_code": "ET002",
        "lecturer_username": "Kalana",
        "day_of_week": "Wednesday",
        "start_time": "13:00",
        "end_time": "15:00",
    },{
        "subject_code": "ET001",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Thursday",
        "start_time": "09:00",
        "end_time": "12:00",
    },
    {
        "subject_code": "ET003",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Thursday",
        "start_time": "13:00",
        "end_time": "15:00",
    },{
        "subject_code": "ET001",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Friday",
        "start_time": "09:00",
        "end_time": "12:00",
    },
    {
        "subject_code": "ET002",
        "lecturer_username": "Kalana",
        "day_of_week": "Friday",
        "start_time": "13:00",
        "end_time": "15:00",
    },
    {
        "subject_code": "ET004",
        "lecturer_username": "Kalana",
        "day_of_week": "Saturday",
        "start_time": "09:00",
        "end_time": "11:00",
    },
    {
        "subject_code": "ET002",
        "lecturer_username": "Kalana",
        "day_of_week": "Saturday",
        "start_time": "12:00",
        "end_time": "14:00",
    },
    {
        "subject_code": "ET001",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Sunday",
        "start_time": "09:00",
        "end_time": "11:00",
    },
    {
        "subject_code": "ET003",
        "lecturer_username": "DidulaAdmin",
        "day_of_week": "Sunday",
        "start_time": "12:00",
        "end_time": "14:00",
    },
    # ... ඔයාගේ timetable rows මෙතනට add කරන්න
]


VALID_DAYS = {
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
}


def _valid_time_format(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except (ValueError, TypeError):
        return False


def insert_subjects():
    added, skipped = 0, 0
    for row in SUBJECTS:
        existing = Subject.query.filter_by(subject_code=row["subject_code"]).first()
        if existing:
            print(f"  [SKIP] Subject '{row['subject_code']}' දැනටමත් තියෙනවා.")
            skipped += 1
            continue

        subject = Subject(
            subject_code=row["subject_code"],
            subject_name=row["subject_name"],
        )
        db.session.add(subject)
        print(f"  [ADD]  Subject '{row['subject_code']}' - {row['subject_name']}")
        added += 1

    db.session.commit()
    print(f"\nSubjects: {added} added, {skipped} skipped.\n")


def insert_timetable():
    added, skipped, errors = 0, 0, 0

    for row in TIMETABLE:
        # --- validation ---
        if row["day_of_week"] not in VALID_DAYS:
            print(f"  [ERROR] Invalid day_of_week: '{row['day_of_week']}' - SKIP කළා.")
            errors += 1
            continue

        if not _valid_time_format(row["start_time"]) or not _valid_time_format(row["end_time"]):
            print(f"  [ERROR] Invalid time format in row: {row} - SKIP කළා.")
            errors += 1
            continue

        subject = Subject.query.filter_by(subject_code=row["subject_code"]).first()
        if subject is None:
            print(f"  [ERROR] Subject code '{row['subject_code']}' සොයාගත නොහැක - "
                  f"SUBJECTS list එකට add කරලාද කියලා check කරන්න. SKIP කළා.")
            errors += 1
            continue

        lecturer = Lecturer.query.filter_by(username=row["lecturer_username"]).first()
        if lecturer is None:
            print(f"  [ERROR] Lecturer username '{row['lecturer_username']}' සොයාගත නොහැක - "
                  f"Admin Panel එකෙන් lecturer මුලින් හදන්න. SKIP කළා.")
            errors += 1
            continue

        # --- duplicate check (same subject + lecturer + day + start_time) ---
        existing = Timetable.query.filter_by(
            subject_id=subject.subject_id,
            lecturer_id=lecturer.lecturer_id,
            day_of_week=row["day_of_week"],
            start_time=row["start_time"],
        ).first()
        if existing:
            print(f"  [SKIP] Timetable row දැනටමත් තියෙනවා: "
                  f"{subject.subject_code} / {lecturer.username} / "
                  f"{row['day_of_week']} {row['start_time']}")
            skipped += 1
            continue

        timetable_entry = Timetable(
            subject_id=subject.subject_id,
            lecturer_id=lecturer.lecturer_id,
            day_of_week=row["day_of_week"],
            start_time=row["start_time"],
            end_time=row["end_time"],
        )
        db.session.add(timetable_entry)
        print(f"  [ADD]  {subject.subject_code} / {lecturer.username} / "
              f"{row['day_of_week']} {row['start_time']}-{row['end_time']}")
        added += 1

    db.session.commit()
    print(f"\nTimetable: {added} added, {skipped} skipped, {errors} errors.\n")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("=== Subjects insert කරමින්... ===")
        insert_subjects()

        print("=== Timetable insert කරමින්... ===")
        insert_timetable()

        print("=== Enrollments sync කරමින් (සියලුම students -> සියලුම subjects)... ===")
        added = sync_all_enrollments()
        print(f"{added} enrollment record(s) added.\n")

        print("Done!")