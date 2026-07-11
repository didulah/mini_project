"""
seed_data.py
============
Fingerprint Attendance System - Sample/Test Data Seeder

මේ script එක run කරන්නේ login -> dashboard flow එක real data එකකින්
end-to-end test කරන්න. Idempotent විදිහට හදලා තියෙන්නේ - කීපවතාවක් run
කළත් duplicate records හැදෙන්නේ නෑ (existing records check කරනවා).

Usage:
    python seed_data.py

Requirements:
    - app.py, extensions.py, models.py already set up (create_app() function
      සහ db object export වෙන්න ඕන)
    - Database tables දැනටමත් create වෙලා තියෙන්න ඕන (app.py first run එකේදී
      db.create_all() call වෙනවා නම් ඒක ඇති)
"""

from datetime import datetime

from app import create_app
from extensions import db
from models import Student, Lecturer, Subject, Enrollment, Timetable


def get_or_create_lecturer(username, password, full_name):
    lecturer = Lecturer.query.filter_by(username=username).first()
    if lecturer:
        print(f"  [SKIP] Lecturer '{username}' already exists.")
        return lecturer

    lecturer = Lecturer(username=username, full_name=full_name)
    lecturer.set_password(password)
    db.session.add(lecturer)
    db.session.commit()
    print(f"  [OK] Lecturer created -> username='{username}', password='{password}'")
    return lecturer


def get_or_create_subject(subject_code, subject_name):
    subject = Subject.query.filter_by(subject_code=subject_code).first()
    if subject:
        print(f"  [SKIP] Subject '{subject_code}' already exists.")
        return subject

    subject = Subject(subject_code=subject_code, subject_name=subject_name)
    db.session.add(subject)
    db.session.commit()
    print(f"  [OK] Subject created -> {subject_code} : {subject_name}")
    return subject


def get_or_create_student(student_id, name, fingerprint_id):
    student = Student.query.get(student_id)
    if student:
        print(f"  [SKIP] Student {student_id} already exists.")
        return student

    student = Student(student_id=student_id, name=name, fingerprint_id=fingerprint_id)
    db.session.add(student)
    db.session.commit()
    print(f"  [OK] Student created -> {student_id} : {name} (fingerprint_id={fingerprint_id})")
    return student


def get_or_create_enrollment(student_id, subject_id):
    existing = Enrollment.query.filter_by(student_id=student_id, subject_id=subject_id).first()
    if existing:
        return existing

    enrollment = Enrollment(student_id=student_id, subject_id=subject_id)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def get_or_create_timetable(subject_id, lecturer_id, day_of_week, start_time, end_time):
    existing = Timetable.query.filter_by(
        subject_id=subject_id,
        lecturer_id=lecturer_id,
        day_of_week=day_of_week,
        start_time=start_time,
    ).first()
    if existing:
        print(f"  [SKIP] Timetable entry for {day_of_week} {start_time}-{end_time} already exists.")
        return existing

    timetable = Timetable(
        subject_id=subject_id,
        lecturer_id=lecturer_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    db.session.add(timetable)
    db.session.commit()
    print(f"  [OK] Timetable entry created -> {day_of_week} {start_time}-{end_time}")
    return timetable


def seed():
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("SEEDING DATABASE - Fingerprint Attendance System")
        print("=" * 60)

        # 1. Lecturer -----------------------------------------------------
        print("\n[1] Lecturer")
        lecturer = get_or_create_lecturer(
            username="lecturer1",
            password="password123",
            full_name="Dr. Nimal Perera",
        )

        # 2. Subject --------------------------------------------------------
        print("\n[2] Subject")
        subject = get_or_create_subject(
            subject_code="ICT3202",
            subject_name="Embedded Systems",
        )

        # 3. Students ---------------------------------------------------------
        print("\n[3] Students")
        sample_students = [
            (249001, "Kasun Silva", 1),
            (249002, "Amaya Fernando", 2),
            (249003, "Tharindu Jayasuriya", 3),
            (249004, "Nethmi Rathnayake", 4),
            (249005, "Dulmini Wickramasinghe", 5),
        ]
        students = [get_or_create_student(sid, name, fid) for sid, name, fid in sample_students]

        # 4. Enrollments ------------------------------------------------------
        print("\n[4] Enrollments")
        for student in students:
            get_or_create_enrollment(student.student_id, subject.subject_id)
        print(f"  [OK] {len(students)} students enrolled in {subject.subject_code}")

        # 5. Timetable (today's day_of_week, so dashboard shows it immediately) --
        print("\n[5] Timetable")
        today_name = datetime.now().strftime("%A")  # e.g. 'Monday'
        get_or_create_timetable(
            subject_id=subject.subject_id,
            lecturer_id=lecturer.lecturer_id,
            day_of_week=today_name,
            start_time="09:00",
            end_time="11:00",
        )

        print("\n" + "=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"Login credentials -> username: lecturer1 | password: password123")
        print(f"Today's timetable entry set for: {today_name} (09:00 - 11:00)")
        print("Now: run 'python app.py', log in, and 'today's lectures' should")
        print("show this Embedded Systems session on the dashboard.")


if __name__ == "__main__":
    seed()