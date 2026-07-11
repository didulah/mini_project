from calendar import monthrange
from datetime import date, datetime

from flask import Blueprint, render_template, session, redirect, url_for, abort, request

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
VALID_STATUSES = ("present", "absent", "excused")
VALID_EXCUSE_REASONS = ("medical", "sport", "other")


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
    save-as-PDF) use කරන්න පුළුවන්.
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


@attendance_bp.route("/student/history")
def student_history():
    """
    Student ID එකක් + මාසයක් (YYYY-MM) දීලා search කරන page එක.

    - student_id query param එක නැත්නම් search form එක විතරක් පෙන්නනවා.
    - student_id එකක් දුන්නාම: ඒ student ලාට enroll වෙච්ච **හැම subject එකකටම**
      වෙන වෙනම card එකක් පෙන්නනවා - ඒ මාසේ පැවැත්වුනු lecture ගණන, absent
      ගණන, attendance %, eligibility (>=80%), සහ දවස් අනුව (daily) attendance
      status එක.
    - Month දෙන්නේ නැත්නම් default එක **මේ මාසයයි**.
    - මේ route එකට access කරන්න ඕන කරන්නේ login වෙච්ච lecturer කෙනෙක් විතරයි -
      ඒත් subject ownership check එකක් නෑ (student ID එකෙන් search කරන එක
      lecturer ඕන කෙනෙක්ටම exam eligibility verify කරගන්න පුළුවන් විදිහට).
    """
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    student_id = request.args.get("student_id", type=int)
    month_str = request.args.get("month")  # e.g. '2026-07'

    student = None
    subject_reports = []
    error = None

    if student_id is not None:
        student = Student.query.get(student_id)

        if student is None:
            error = f"Student ID {student_id} සොයාගත නොහැක."
        else:
            today = date.today()
            try:
                year, month = (int(part) for part in month_str.split("-"))
            except (AttributeError, ValueError):
                year, month = today.year, today.month
            month_str = f"{year:04d}-{month:02d}"

            month_start = date(year, month, 1)
            month_end = date(year, month, monthrange(year, month)[1])

            enrolled_subjects = (
                Subject.query.join(Enrollment, Enrollment.subject_id == Subject.subject_id)
                .filter(Enrollment.student_id == student_id)
                .order_by(Subject.subject_name)
                .all()
            )

            for subject in enrolled_subjects:
                timetable_ids = [
                    t.timetable_id
                    for t in Timetable.query.filter_by(subject_id=subject.subject_id).all()
                ]

                sessions_in_month = (
                    LectureSession.query.filter(
                        LectureSession.timetable_id.in_(timetable_ids),
                        LectureSession.session_date >= month_start,
                        LectureSession.session_date <= month_end,
                    )
                    .order_by(LectureSession.session_date)
                    .all()
                    if timetable_ids
                    else []
                )
                session_ids = [s.session_id for s in sessions_in_month]
                total_sessions = len(session_ids)

                records_by_session = (
                    {
                        r.session_id: r
                        for r in AttendanceRecord.query.filter(
                            AttendanceRecord.student_id == student_id,
                            AttendanceRecord.session_id.in_(session_ids),
                        ).all()
                    }
                    if session_ids
                    else {}
                )

                daily_rows = []
                attended = 0
                absent = 0
                for lecture_session_obj in sessions_in_month:
                    record = records_by_session.get(lecture_session_obj.session_id)
                    status = record.status if record else "absent"
                    if status in ("present", "excused"):
                        attended += 1
                    else:
                        absent += 1
                    daily_rows.append(
                        {
                            "date": lecture_session_obj.session_date,
                            "status": status,
                            "excuse_reason": record.excuse_reason if record else None,
                        }
                    )

                percent = (
                    round(100.0 * attended / total_sessions, 2) if total_sessions else 0.0
                )

                subject_reports.append(
                    {
                        "subject": subject,
                        "total_sessions": total_sessions,
                        "attended": attended,
                        "absent": absent,
                        "percent": percent,
                        "eligible": percent >= ELIGIBILITY_THRESHOLD,
                        "daily_rows": daily_rows,
                    }
                )

    return render_template(
        "student_history.html",
        student=student,
        student_id_query=student_id,
        month=month_str,
        subject_reports=subject_reports,
        error=error,
        threshold=ELIGIBILITY_THRESHOLD,
    )


@attendance_bp.route("/attendance/update/<int:record_id>", methods=["GET", "POST"])
def update_attendance(record_id):
    """
    Attendance record එකක් lecturer ට manually update කරන්න පුළුවන් screen එක.
    Use case දෙකක් cover කරනවා:

      1. False-absent correction - fingerprint scan එක fail වෙලා 'absent'
         ලෙස පෙන්නුනු student කෙනෙක් ඇත්තටම class එකට ආවා නම්, status එක
         'present' ලෙස manually flip කරනවා.
      2. Excuse handling - class එකට නොපැමිනි student කෙනෙක් පස්සේ medical/
         sport/other reason එකක් ඉදිරිපත් කළොත්, status එක 'excused' ලෙස
         දාලා reason එකත් save කරනවා. (report/eligibility calculation එකේදී
         excused = attended ලෙසයි ගණන් ගන්නේ - report()/student_history()
         දෙකෙහිම status in ('present','excused') check එක බලන්න.)

    Ownership check එක start_session()/session_view()/report() වල තියෙන
    pattern එකම - record එකේ session එකේ timetable එකේ lecturer_id != current
    lecturer නම් 403.
    """
    if not _lecturer_logged_in():
        return redirect(url_for("auth.login"))

    record = AttendanceRecord.query.get_or_404(record_id)
    lecture_session = record.session
    timetable_entry = lecture_session.timetable_entry

    if timetable_entry.lecturer_id != session["lecturer_id"]:
        abort(403)

    student = record.student
    subject = timetable_entry.subject
    error = None

    if request.method == "POST":
        new_status = request.form.get("status")
        excuse_reason = request.form.get("excuse_reason") or None

        if new_status not in VALID_STATUSES:
            abort(400)

        if new_status == "excused" and excuse_reason not in VALID_EXCUSE_REASONS:
            error = "Excused ලෙස සලකුණු කරන්න excuse reason එකක් (medical/sport/other) තෝරන්න ඕන."
        else:
            record.status = new_status
            record.excuse_reason = excuse_reason if new_status == "excused" else None

            if new_status == "present" and record.marked_time is None:
                # Manually 'present' කරද්දී marked_time කලින් තිබ්බේ නැත්නම්
                # දැන් වෙලාව audit trail එකක් විදිහට save කරනවා.
                record.marked_time = datetime.utcnow()
            elif new_status == "absent":
                record.marked_time = None

            record.updated_by = session["lecturer_id"]
            record.updated_at = datetime.utcnow()

            db.session.commit()

            return redirect(url_for("attendance.session_view", session_id=lecture_session.session_id))

    return render_template(
        "attendance_update.html",
        record=record,
        student=student,
        subject=subject,
        lecture_session=lecture_session,
        error=error,
    )