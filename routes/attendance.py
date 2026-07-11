from datetime import date

from flask import Blueprint, render_template, session, redirect, url_for, abort

from extensions import db
from models import Timetable, LectureSession, Student, Enrollment, AttendanceRecord

attendance_bp = Blueprint("attendance", __name__)


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
    වෙනවා, page refresh කළාම ඒ වෙනස පේනවා (real-time push - websockets - තවම
    scope එකේ නෑ, plain refresh එකින් වැඩේ කරගන්න පුළුවන්).
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

    # session එකට attendance_records row එකක් නැති students ලාට default
    # 'absent' row එකක් හදනවා (session ආරම්භයේදීම හැමෝම absent, scan වුනාම present)
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


# ------------------------------------------------------------------
# TODO (next steps - not yet implemented):
#
# @attendance_bp.route("/report")
#   -> full attendance report across all students, with a
#      printable view (see docx/pdf skill for generating the export).
#
# @attendance_bp.route("/student/<int:student_id>/history")
#   -> monthly historical data + attendance % + eligibility
#      (uses the query pattern documented at the bottom of schema.sql).
#
# @attendance_bp.route("/attendance/update/<int:record_id>", methods=["GET", "POST"])
#   -> lecturer corrects a false-absent mark, or applies an
#      excuse_reason (medical/sport/other) to flip absent -> present.
# ------------------------------------------------------------------