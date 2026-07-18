"""
Admin blueprint - restricted to lecturers with is_admin = True.

Routes:
    GET  /admin/dashboard      -> overview + links
    GET  /admin/students       -> list all students
    GET  /admin/lecturers      -> list all lecturers
    GET/POST /admin/add_student   -> create a new student
                                     (auto-enrolled into ALL subjects - no
                                      manual subject selection needed anymore)
    GET/POST /admin/add_lecturer  -> create a new lecturer (optionally as admin)
    GET/POST /admin/assign_fingerprint -> attach fingerprint_id to a student,
                                     either manually or by triggering live
                                     hardware enrollment on the ESP32
    POST /admin/start_enrollment/<student_id>  -> switch device to ENROLLMENT mode
    POST /admin/cancel_enrollment              -> switch device back to ATTENDANCE mode
    GET  /admin/enrollment_status              -> JSON, polled by the page's JS

    POST /admin/start_delete_fingerprint/<student_id>  -> switch device to DELETE mode
    POST /admin/cancel_delete_fingerprint              -> switch device back to ATTENDANCE mode
"""
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from extensions import db
from models import Student, Lecturer, Subject, Enrollment, DeviceState, sync_all_enrollments

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# Access control helpers
# ---------------------------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "lecturer_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "lecturer_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("auth.login"))
        lecturer = Lecturer.query.get(session["lecturer_id"])
        if not lecturer or not lecturer.is_admin:
            flash("Admin access required.")
            return redirect(url_for("attendance.dashboard"))
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/dashboard")
@admin_required
def admin_dashboard():
    student_count = Student.query.count()
    lecturer_count = Lecturer.query.count()
    subject_count = Subject.query.count()
    unenrolled_fingerprint_count = Student.query.filter(Student.fingerprint_id.is_(None)).count()

    return render_template(
        "admin_dashboard.html",
        student_count=student_count,
        lecturer_count=lecturer_count,
        subject_count=subject_count,
        unenrolled_fingerprint_count=unenrolled_fingerprint_count,
    )


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
@admin_bp.route("/students")
@admin_required
def list_students():
    students = Student.query.order_by(Student.student_id).all()
    return render_template("admin_students.html", students=students)


@admin_bp.route("/add_student", methods=["GET", "POST"])
@admin_required
def add_student():
    if request.method == "POST":
        student_id_raw = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        fingerprint_id_raw = request.form.get("fingerprint_id", "").strip()

        # --- Validation ---
        if not student_id_raw.isdigit() or not name:
            flash("Student ID (numbers only) and Name are required.")
            return render_template("admin_add_student.html")

        student_id = int(student_id_raw)

        if Student.query.get(student_id):
            flash(f"Student ID {student_id} already exists.")
            return render_template("admin_add_student.html")

        fingerprint_id = None
        if fingerprint_id_raw:
            if not fingerprint_id_raw.isdigit():
                flash("Fingerprint ID must be a number.")
                return render_template("admin_add_student.html")
            fingerprint_id = int(fingerprint_id_raw)
            if Student.query.filter_by(fingerprint_id=fingerprint_id).first():
                flash(f"Fingerprint ID {fingerprint_id} is already assigned to another student.")
                return render_template("admin_add_student.html")

        # --- Create student ---
        student = Student(student_id=student_id, name=name, fingerprint_id=fingerprint_id)
        db.session.add(student)
        db.session.commit()

        # --- Auto-enroll into every existing subject ---
        # (subject selection removed - every student takes every subject now)
        sync_all_enrollments()

        flash(f"Student {name} ({student_id}) added and enrolled in all subjects.")
        return redirect(url_for("admin.list_students"))

    return render_template("admin_add_student.html")


@admin_bp.route("/assign_fingerprint", methods=["GET", "POST"])
@admin_required
def assign_fingerprint():
    """
    Manage fingerprint templates for students. Three things happen on
    this one page now:

      1. Live hardware ENROLLMENT (preferred) - click "Start Enrollment"
         next to a student without a fingerprint. Flips the device into
         ENROLLMENT mode (see start_enrollment below). The page
         auto-refreshes and shows the result once the ESP32 reports back.

      2. Live hardware DELETE (new) - click "Remove Fingerprint" next to
         a student who already has one. Flips the device into DELETE
         mode (see start_delete_fingerprint below). Removes the template
         from the R307S sensor itself AND clears fingerprint_id in the DB.

      3. Manual entry (fallback) - if you already know the fingerprint_id,
         the original manual form below still works exactly as before.
    """
    unenrolled = (
        Student.query.filter(Student.fingerprint_id.is_(None))
        .order_by(Student.student_id)
        .all()
    )
    enrolled = (
        Student.query.filter(Student.fingerprint_id.isnot(None))
        .order_by(Student.student_id)
        .all()
    )
    device_state = DeviceState.get_singleton()

    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        fingerprint_id_raw = request.form.get("fingerprint_id", "").strip()

        student = Student.query.get(student_id)
        if not student:
            flash("Student not found.")
            return redirect(url_for("admin.assign_fingerprint"))

        if not fingerprint_id_raw.isdigit():
            flash("Fingerprint ID must be a number.")
            return redirect(url_for("admin.assign_fingerprint"))

        fingerprint_id = int(fingerprint_id_raw)
        existing = Student.query.filter_by(fingerprint_id=fingerprint_id).first()
        if existing:
            flash(
                f"Fingerprint ID {fingerprint_id} is already assigned to "
                f"{existing.name} ({existing.student_id})."
            )
            return redirect(url_for("admin.assign_fingerprint"))

        student.fingerprint_id = fingerprint_id
        db.session.commit()
        flash(f"Fingerprint ID {fingerprint_id} assigned to {student.name}.")
        return redirect(url_for("admin.assign_fingerprint"))

    return render_template(
        "admin_assign_fingerprint.html",
        students=unenrolled,
        enrolled_students=enrolled,
        device_state=device_state,
    )


@admin_bp.route("/start_enrollment/<int:student_id>", methods=["POST"])
@admin_required
def start_enrollment(student_id):
    """Switches the device into ENROLLMENT mode for one specific student.
    The ESP32 picks this up on its next /api/poll (within a few seconds)
    and starts asking for a fingerprint scan."""
    student = Student.query.get(student_id)
    if not student:
        flash("Student not found.")
        return redirect(url_for("admin.assign_fingerprint"))

    if student.fingerprint_id is not None:
        flash(f"{student.name} already has a fingerprint assigned.")
        return redirect(url_for("admin.assign_fingerprint"))

    state = DeviceState.get_singleton()
    state.mode = "ENROLLMENT"
    state.enroll_student_id = student.student_id
    state.enroll_status = "waiting"
    state.enroll_message = None
    state.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Enrollment mode started for {student.name}. Ask them to scan their finger on the device now.")
    return redirect(url_for("admin.assign_fingerprint"))


@admin_bp.route("/cancel_enrollment", methods=["POST"])
@admin_required
def cancel_enrollment():
    """Manually abort a stuck/unwanted enrollment and hand the device
    back to normal ATTENDANCE mode."""
    state = DeviceState.get_singleton()
    state.mode = "ATTENDANCE"
    state.enroll_student_id = None
    state.enroll_status = "idle"
    state.enroll_message = None
    state.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Enrollment mode cancelled - device is back in Attendance mode.")
    return redirect(url_for("admin.assign_fingerprint"))


@admin_bp.route("/enrollment_status")
@admin_required
def enrollment_status():
    """JSON polling endpoint used by admin_assign_fingerprint.html's JS to
    show live enrollment progress without a full page refresh."""
    state = DeviceState.get_singleton()
    return jsonify({
        "mode": state.mode,
        "enroll_student_id": state.enroll_student_id,
        "enroll_status": state.enroll_status,
        "enroll_message": state.enroll_message,
    })


# ---------------------------------------------------------------------------
# NEW - Delete fingerprint (mirrors the enrollment routes above)
# ---------------------------------------------------------------------------
@admin_bp.route("/start_delete_fingerprint/<int:student_id>", methods=["POST"])
@admin_required
def start_delete_fingerprint(student_id):
    """Switches the device into DELETE mode for one specific student's
    fingerprint. The ESP32 picks this up on its next /api/poll and
    removes the matching template from the R307S sensor itself."""
    student = Student.query.get(student_id)
    if not student:
        flash("Student not found.")
        return redirect(url_for("admin.assign_fingerprint"))

    if student.fingerprint_id is None:
        flash(f"{student.name} has no fingerprint enrolled.")
        return redirect(url_for("admin.assign_fingerprint"))

    state = DeviceState.get_singleton()
    state.mode = "DELETE"
    state.delete_student_id = student.student_id
    state.delete_status = "waiting"
    state.delete_message = None
    state.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Delete mode started for {student.name}'s fingerprint. Device will remove it from the sensor now.")
    return redirect(url_for("admin.assign_fingerprint"))


@admin_bp.route("/cancel_delete_fingerprint", methods=["POST"])
@admin_required
def cancel_delete_fingerprint():
    """Manually abort a stuck/unwanted delete and hand the device back
    to normal ATTENDANCE mode."""
    state = DeviceState.get_singleton()
    state.mode = "ATTENDANCE"
    state.delete_student_id = None
    state.delete_status = "idle"
    state.delete_message = None
    state.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Delete mode cancelled - device is back in Attendance mode.")
    return redirect(url_for("admin.assign_fingerprint"))


# ---------------------------------------------------------------------------
# Lecturers
# ---------------------------------------------------------------------------
@admin_bp.route("/lecturers")
@admin_required
def list_lecturers():
    lecturers = Lecturer.query.order_by(Lecturer.lecturer_id).all()
    return render_template("admin_lecturers.html", lecturers=lecturers)


@admin_bp.route("/add_lecturer", methods=["GET", "POST"])
@admin_required
def add_lecturer():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        make_admin = request.form.get("is_admin") == "on"

        if not username or not password or not full_name:
            flash("Username, Password and Full Name are all required.")
            return render_template("admin_add_lecturer.html")

        if Lecturer.query.filter_by(username=username).first():
            flash(f"Username '{username}' is already taken.")
            return render_template("admin_add_lecturer.html")

        lecturer = Lecturer(username=username, full_name=full_name, is_admin=make_admin)
        lecturer.set_password(password)
        db.session.add(lecturer)
        db.session.commit()

        flash(f"Lecturer '{full_name}' added successfully.")
        return redirect(url_for("admin.list_lecturers"))

    return render_template("admin_add_lecturer.html")