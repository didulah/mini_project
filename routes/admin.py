"""
Admin blueprint - restricted to lecturers with is_admin = True.

Routes:
    GET  /admin/dashboard      -> overview + links
    GET  /admin/students       -> list all students
    GET  /admin/lecturers      -> list all lecturers
    GET/POST /admin/add_student   -> create a new student (+ subject enrollment)
    GET/POST /admin/add_lecturer  -> create a new lecturer (optionally as admin)
"""
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from extensions import db
from models import Student, Lecturer, Subject, Enrollment

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
    subjects = Subject.query.order_by(Subject.subject_code).all()

    if request.method == "POST":
        student_id_raw = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        fingerprint_id_raw = request.form.get("fingerprint_id", "").strip()
        subject_ids = request.form.getlist("subject_ids")  # list of strings

        # --- Validation ---
        if not student_id_raw.isdigit() or not name:
            flash("Student ID (numbers only) and Name are required.")
            return render_template("admin_add_student.html", subjects=subjects)

        student_id = int(student_id_raw)

        if Student.query.get(student_id):
            flash(f"Student ID {student_id} already exists.")
            return render_template("admin_add_student.html", subjects=subjects)

        fingerprint_id = None
        if fingerprint_id_raw:
            if not fingerprint_id_raw.isdigit():
                flash("Fingerprint ID must be a number.")
                return render_template("admin_add_student.html", subjects=subjects)
            fingerprint_id = int(fingerprint_id_raw)
            if Student.query.filter_by(fingerprint_id=fingerprint_id).first():
                flash(f"Fingerprint ID {fingerprint_id} is already assigned to another student.")
                return render_template("admin_add_student.html", subjects=subjects)

        # --- Create student ---
        student = Student(student_id=student_id, name=name, fingerprint_id=fingerprint_id)
        db.session.add(student)

        # --- Subject enrollment ---
        for sid in subject_ids:
            db.session.add(Enrollment(student_id=student_id, subject_id=int(sid)))

        db.session.commit()
        flash(f"Student {name} ({student_id}) added successfully.")
        return redirect(url_for("admin.list_students"))

    return render_template("admin_add_student.html", subjects=subjects)

@admin_bp.route("/assign_fingerprint", methods=["GET", "POST"])
@admin_required
def assign_fingerprint():
    """
    Attach a hardware fingerprint template ID (captured on the R307S
    sensor's own onboard enrollment mode) to an existing student record.
    """
    unenrolled = (
        Student.query.filter(Student.fingerprint_id.is_(None))
        .order_by(Student.student_id)
        .all()
    )

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

    return render_template("admin_assign_fingerprint.html", students=unenrolled)

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