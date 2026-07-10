-- ============================================================
-- Fingerprint Attendance System - Database Schema (SQLite)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- STUDENTS
-- ------------------------------------------------------------
CREATE TABLE students (
    student_id      INTEGER PRIMARY KEY,   -- e.g. 249001 (entered manually, not autoincrement)
    name            TEXT NOT NULL,
    fingerprint_id  INTEGER UNIQUE,        -- ID assigned by the R307S sensor's internal storage slot
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- LECTURERS
-- ------------------------------------------------------------
CREATE TABLE lecturers (
    lecturer_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- SUBJECTS
-- ------------------------------------------------------------
CREATE TABLE subjects (
    subject_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_code    TEXT NOT NULL UNIQUE,
    subject_name    TEXT NOT NULL
);

-- ------------------------------------------------------------
-- ENROLLMENTS  (which students belong to which subject/batch)
-- ------------------------------------------------------------
CREATE TABLE enrollments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(student_id),
    subject_id      INTEGER NOT NULL REFERENCES subjects(subject_id),
    UNIQUE(student_id, subject_id)
);

-- ------------------------------------------------------------
-- TIMETABLE  (weekly recurring schedule)
-- ------------------------------------------------------------
CREATE TABLE timetable (
    timetable_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id      INTEGER NOT NULL REFERENCES subjects(subject_id),
    lecturer_id     INTEGER NOT NULL REFERENCES lecturers(lecturer_id),
    day_of_week     TEXT NOT NULL CHECK (day_of_week IN
                        ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')),
    start_time      TEXT NOT NULL,   -- e.g. '09:00'
    end_time        TEXT NOT NULL    -- e.g. '11:00'
);

-- ------------------------------------------------------------
-- LECTURE_SESSIONS  (an actual date-specific instance of a lecture)
-- ------------------------------------------------------------
CREATE TABLE lecture_sessions (
    session_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    timetable_id    INTEGER NOT NULL REFERENCES timetable(timetable_id),
    session_date    DATE NOT NULL,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at        TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed')),
    UNIQUE(timetable_id, session_date)
);

-- ------------------------------------------------------------
-- ATTENDANCE_RECORDS
-- ------------------------------------------------------------
CREATE TABLE attendance_records (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES lecture_sessions(session_id),
    student_id      INTEGER NOT NULL REFERENCES students(student_id),
    status          TEXT NOT NULL DEFAULT 'absent' CHECK (status IN ('present','absent','excused')),
    marked_time     TIMESTAMP,               -- fingerprint scan time; NULL if absent
    excuse_reason   TEXT CHECK (excuse_reason IN ('medical','sport','other') OR excuse_reason IS NULL),
    updated_by      INTEGER REFERENCES lecturers(lecturer_id),  -- who last manually edited this record
    updated_at      TIMESTAMP,
    UNIQUE(session_id, student_id)
);

-- ------------------------------------------------------------
-- Useful indexes for common queries
-- ------------------------------------------------------------
CREATE INDEX idx_attendance_student ON attendance_records(student_id);
CREATE INDEX idx_attendance_session ON attendance_records(session_id);
CREATE INDEX idx_sessions_date ON lecture_sessions(session_date);
CREATE INDEX idx_timetable_day ON timetable(day_of_week);

-- ------------------------------------------------------------
-- Example: attendance % calculation for a student in a subject
-- (used to decide eligible / not eligible, threshold = 80%)
-- ------------------------------------------------------------
-- SELECT
--     s.student_id, s.name,
--     COUNT(ar.record_id) AS total_sessions,
--     SUM(CASE WHEN ar.status IN ('present','excused') THEN 1 ELSE 0 END) AS attended,
--     ROUND(100.0 * SUM(CASE WHEN ar.status IN ('present','excused') THEN 1 ELSE 0 END)
--           / COUNT(ar.record_id), 2) AS attendance_percent
-- FROM students s
-- JOIN attendance_records ar ON ar.student_id = s.student_id
-- JOIN lecture_sessions ls ON ls.session_id = ar.session_id
-- JOIN timetable t ON t.timetable_id = ls.timetable_id
-- WHERE s.student_id = ? AND t.subject_id = ?
-- GROUP BY s.student_id;