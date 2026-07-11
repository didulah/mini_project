from datetime import date, datetime

from flask import Blueprint, render_template, session, redirect, url_for, abort

from extensions import db
from models import (
    Timetable,
    LectureSession,
    Student,
    Subject,
    Enrollment,
    AttendanceRecord,
)

attendance_bp = Blueprint("attendance", __name__)

ELIGIBILITY_THRESHOLD = 80.0


def _lecturer_logged_in():
    return "lecturer_id" in session


@attendance_bp.route("/dashboard")
def dashboard():
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    today_name = date.today().strftime("%A")  # 'Monday', 'Tuesday', ...
    todays_lectures = Timetable.query.filter_by(
        lecturer_id=session["lecturer_id"], day_of_week=today_name
    ).all()

    return render_template("dashboard.html", lectures=todays_lectures, today=today_name)


@attendance_bp.route("/session/start/<int:timetable_id>", methods=["POST"])
def start_session(timetable_id):
    """
    'Start Session' button එකෙන් call වෙන route එක.

    - timetable_id එක අද දවසේ මේ lecturer ට අයිති row එකක්ද කියලා verify කරනවා
      (වෙන lecturer කෙනෙක්ගේ session එකක් accidentally start කරගන්නෑ).
    - අද දවසට lecture_sessions row එකක් දැනටමත් තියෙනවා නම් (double-click, page
      refresh, etc.) ඒකම ආපහු use කරනවා - duplicate sessions හැදෙන්නෑ.
    - අලුතින් session එකක් නම්, status='active' කරලා DB එකට දානවා.
    """
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    timetable_entry = Timetable.query.get_or_404(timetable_id)

    if timetable_entry.lecturer_id != session["lecturer_id"]:
        abort(403)

    today = date.today()
    lecture_session = LectureSession.query.filter_by(
        timetable_id=timetable_id, session_date=today
    ).first()

    if lecture_session is None:
        lecture_session = LectureSession(
            timetable_id=timetable_id,
            session_date=today,
            status="active",
        )
        db.session.add(lecture_session)
        db.session.commit()

    return redirect(url_for("attendance.session_view", session_id=lecture_session.session_id))


@attendance_bp.route("/session/<int:session_id>")
def session_view(session_id):
    """
    Session එක start කළාට පස්සේ redirect වෙන 'live attendance' screen එක.
    Enrolled students ලා ඔක්කොම (default status='absent' ලෙස) පෙන්නනවා -
    fingerprint scan එකක් ආවම (/api/scan හරහා) status එක 'present' ලෙස update
    වෙනවා, page refresh කළාම ඒ වෙනස පේනවා.
    """
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    lecture_session = LectureSession.query.get_or_404(session_id)
    timetable_entry = lecture_session.timetable_entry

    if timetable_entry.lecturer_id != session["lecturer_id"]:
        abort(403)

    subject = timetable_entry.subject

    enrolled_students = (
        Student.query.join(Enrollment, Enrollment.student_id == Student.student_id)
        .filter(Enrollment.subject_id == subject.subject_id)
        .order_by(Student.student_id)
        .all()
    )

    existing_ids = {
        r.student_id
        for r in AttendanceRecord.query.filter_by(session_id=session_id).all()
    }
    created_any = False
    for student in enrolled_students:
        if student.student_id not in existing_ids:
            db.session.add(
                AttendanceRecord(
                    session_id=session_id,
                    student_id=student.student_id,
                    status="absent",
                )
            )
            created_any = True
    if created_any:
        db.session.commit()

    records_by_student = {
        r.student_id: r
        for r in AttendanceRecord.query.filter_by(session_id=session_id).all()
    }

    present_count = sum(1 for r in records_by_student.values() if r.status == "present")

    return render_template(
        "session.html",
        lecture_session=lecture_session,
        subject=subject,
        students=enrolled_students,
        records=records_by_student,
        present_count=present_count,
        total_count=len(enrolled_students),
    )


@attendance_bp.route("/report")
def report_subjects():
    """
    Report එකට යනකොට මුලින්ම subject එකක් තෝරගන්න ඕන (lecturer කෙනෙක්ට
    subject කීපයක් teach කරන්න පුළුවන් නිසා). ලොග් වෙලා ඉන්න lecturer ගේ
    timetable එකේ තියෙන subjects විතරක් පෙන්නනවා.
    """
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    subjects = (
        Subject.query.join(Timetable, Timetable.subject_id == Subject.subject_id)
        .filter(Timetable.lecturer_id == session["lecturer_id"])
        .distinct()
        .order_by(Subject.subject_name)
        .all()
    )

    return render_template("report_subjects.html", subjects=subjects)


@attendance_bp.route("/report/<int:subject_id>")
def report(subject_id):
    """
    Subject එකකට enroll වෙච්ච සියලුම students ලාගේ attendance summary එක:
    total sessions held, attended count, absent count, attendance %,
    eligibility (>= 80% => eligible). Printable විදිහටත් (browser print /
    save-as-PDF) use කරන්න පුළුවන් - report.html එකේ .no-print class එකෙන්
    print මොඩ් එකේදී buttons/nav hide වෙනවා.
    """
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    subject = Subject.query.get_or_404(subject_id)

    timetable_ids = [
        t.timetable_id
        for t in Timetable.query.filter_by(
            subject_id=subject_id, lecturer_id=session["lecturer_id"]
        ).all()
    ]
    if not timetable_ids:
        # මේ lecturer මේ subject එක teach කරන්නේ නෑ නම් access නෑ
        abort(403)

    sessions_held = LectureSession.query.filter(
        LectureSession.timetable_id.in_(timetable_ids)
    ).all()
    session_ids = [s.session_id for s in sessions_held]
    total_sessions = len(session_ids)

    enrolled_students = (
        Student.query.join(Enrollment, Enrollment.student_id == Student.student_id)
        .filter(Enrollment.subject_id == subject_id)
        .order_by(Student.student_id)
        .all()
    )

    rows = []
    for student in enrolled_students:
        attended = absent = 0
        percent = 0.0

        if total_sessions > 0:
            records = AttendanceRecord.query.filter(
                AttendanceRecord.student_id == student.student_id,
                AttendanceRecord.session_id.in_(session_ids),
            ).all()
            attended = sum(1 for r in records if r.status in ("present", "excused"))
            absent = sum(1 for r in records if r.status == "absent")
            percent = round(100.0 * attended / total_sessions, 2)

        rows.append(
            {
                "student": student,
                "attended": attended,
                "absent": absent,
                "percent": percent,
                "eligible": percent >= ELIGIBILITY_THRESHOLD,
            }
        )

    return render_template(
        "report.html",
        subject=subject,
        total_sessions=total_sessions,
        rows=rows,
        threshold=ELIGIBILITY_THRESHOLD,
        generated_at=datetime.now(),
    )


# ------------------------------------------------------------------
# TODO (next steps - not yet implemented):
#
# @attendance_bp.route("/student/<int:student_id>/history")
#   -> monthly historical data + attendance % + eligibility
#      (uses the query pattern documented at the bottom of schema.sql).
#
# @attendance_bp.route("/attendance/update/<int:record_id>", methods=["GET", "POST"])
#   -> lecturer corrects a false-absent mark, or applies an
#      excuse_reason (medical/sport/other) to flip absent -> present.
# ------------------------------------------------------------------