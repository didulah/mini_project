from datetime import date

from flask import Blueprint, render_template, session, redirect, url_for

from models import Timetable

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


# ------------------------------------------------------------------
# TODO (next steps - not yet implemented):
#
# @attendance_bp.route("/session/start/<int:timetable_id>")
#   -> creates a lecture_sessions row for today, redirects to a
#      "live attendance" screen the ESP32 can post scans against.
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
