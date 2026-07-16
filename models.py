"""
SQLAlchemy models - directly mirrors schema.sql
(students, lecturers, subjects, enrollments, timetable,
lecture_sessions, attendance_records)
"""
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

# Sri Lanka = UTC+5:30. Database එකේ marked_time/started_at/ended_at ඔක්කොම
# datetime.utcnow() එකෙන් UTC ලෙසයි save වෙන්නේ (server location වෙනස් උනත්
# consistent data තියෙන්න - good practice). Display කරන කොට විතරයි local
# time එකට convert කරන්න ඕන - ඒකට AttendanceRecord.marked_time_local property එක.
SRI_LANKA_OFFSET = timedelta(hours=5, minutes=30)


class Student(db.Model):
    __tablename__ = "students"

    student_id = db.Column(db.Integer, primary_key=True)  # e.g. 249001, entered manually
    name = db.Column(db.String(120), nullable=False)
    fingerprint_id = db.Column(db.Integer, unique=True)  # nullable - assigned later during hardware enrollment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship("Enrollment", backref="student", lazy=True)
    attendance_records = db.relationship("AttendanceRecord", backref="student", lazy=True)

    def __repr__(self):
        return f"<Student {self.student_id} - {self.name}>"


class Lecturer(db.Model):
    __tablename__ = "lecturers"

    lecturer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)  # NEW: admin panel access
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    timetable_entries = db.relationship("Timetable", backref="lecturer", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Lecturer {self.username}>"


class Subject(db.Model):
    __tablename__ = "subjects"

    subject_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_code = db.Column(db.String(20), nullable=False, unique=True)
    subject_name = db.Column(db.String(150), nullable=False)

    enrollments = db.relationship("Enrollment", backref="subject", lazy=True)
    timetable_entries = db.relationship("Timetable", backref="subject", lazy=True)

    def __repr__(self):
        return f"<Subject {self.subject_code}>"


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.student_id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.subject_id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("student_id", "subject_id"),)


class Timetable(db.Model):
    __tablename__ = "timetable"

    timetable_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.subject_id"), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey("lecturers.lecturer_id"), nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)  # 'Monday' .. 'Sunday'
    start_time = db.Column(db.String(5), nullable=False)     # '09:00'
    end_time = db.Column(db.String(5), nullable=False)

    sessions = db.relationship("LectureSession", backref="timetable_entry", lazy=True)

    def __repr__(self):
        return f"<Timetable {self.day_of_week} {self.start_time}-{self.end_time}>"


class LectureSession(db.Model):
    __tablename__ = "lecture_sessions"

    session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timetable_id = db.Column(db.Integer, db.ForeignKey("timetable.timetable_id"), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    status = db.Column(db.String(10), nullable=False, default="active")  # active / closed

    __table_args__ = (db.UniqueConstraint("timetable_id", "session_date"),)

    attendance_records = db.relationship("AttendanceRecord", backref="session", lazy=True)

    def __repr__(self):
        return f"<LectureSession {self.session_date} ({self.status})>"


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    record_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("lecture_sessions.session_id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.student_id"), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="absent")  # present/absent/excused
    marked_time = db.Column(db.DateTime)
    excuse_reason = db.Column(db.String(10))  # medical / sport / other
    updated_by = db.Column(db.Integer, db.ForeignKey("lecturers.lecturer_id"))
    updated_at = db.Column(db.DateTime)

    __table_args__ = (db.UniqueConstraint("session_id", "student_id"),)

    @property
    def marked_time_local(self):
        """UTC marked_time එක Sri Lanka local time (UTC+5:30) එකට convert
        කරලා දෙනවා - templates වල display කරන්න use කරන්න."""
        return self.marked_time + SRI_LANKA_OFFSET if self.marked_time else None

    def __repr__(self):
        return f"<AttendanceRecord session={self.session_id} student={self.student_id} {self.status}>"


# ---------------------------------------------------------------------------
# NEW: "every student takes every subject" enrollment model
# ---------------------------------------------------------------------------
def sync_all_enrollments():
    """
    Idempotent helper - Database එකේ ඉන්න සියලුම students, දැනට ඉන්න
    සියලුම subjects වලට enroll වෙලා ඉන්නවා කියලා සහතික කරනවා.

    මොකද call කරන්නේ:
      - අලුත් student එකක් add කරාම (subject select කරන්නේ නැති නිසා,
        ඒ student ව දැනට ඉන්න සියලුම subjects වලට auto-enroll කරන්න)
      - අලුත් subject එකක් add කරාම (insert_timetable.py වගේ script එකකින්
        subject එකක් add කරාම, දැනටමත් ඉන්න students ලා ඒකටත් auto-enroll
        කරන්න)

    දෙපැත්තෙන්ම already-enrolled pairs skip කරලා, අඩුවෙන් ඉන්න
    enrollments විතරක් INSERT කරනවා - ඒ නිසා කීපවතාවක් run කලත් error/
    duplicate risk එකක් නෑ.

    Returns: අලුතෙන් insert උනු enrollment record ගණන (int)
    """
    all_student_ids = [row.student_id for row in Student.query.all()]
    all_subject_ids = [row.subject_id for row in Subject.query.all()]

    existing_pairs = {
        (e.student_id, e.subject_id) for e in Enrollment.query.all()
    }

    added = 0
    for student_id in all_student_ids:
        for subject_id in all_subject_ids:
            if (student_id, subject_id) not in existing_pairs:
                db.session.add(Enrollment(student_id=student_id, subject_id=subject_id))
                added += 1

    if added:
        db.session.commit()

    return added