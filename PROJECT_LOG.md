# PROJECT_LOG.md — Fingerprint Attendance System

_Last updated: this session (Admin Panel implementation)_

## 🎯 Original Goal
Fingerprint sensor (R307S) + ESP32 based Student Attendance Management System — hardware device එක Flask web app (SQLite database) එකකට integrate කරන project එකක්. Lecturer login → today's lectures → session start/live attendance → printable reports → student monthly history (eligibility ≥80%) → false-absent correction + medical/sport/other excuse handling → **Admin Panel for student/lecturer onboarding**.

GitHub repo: https://github.com/didulah/mini_project (user: didulah)

### Core requirements
- Sensor scan → attendance auto-mark (hardware, postponed)
- Lecturer login → today's lectures → select
- All-students printable attendance report
- Student ID → monthly historical data with eligibility %
- Update Attendance: false-absent correction + excuse handling
- Database + suitable deployment
- **Admin Panel: add students (+ subject enrollment) and add lecturers, self-service, no manual DB edits**

---

## 🧩 Hardware (postponed, unchanged)
R307S, ESP32 (38-pin), RTC DS3231, OLED 0.91" (4-pin), Buzzer, S8050 transistor, charging module + 3.7V battery. `/api/scan` already hardware-agnostic (JSON: `fingerprint_id` + `session_id`).

---

## 🏗️ Architecture Decisions (all confirmed)
- Session-based attendance mapping (lecturer "Start Session" → only then scans map to it)
- `/api/scan` POST endpoint, JSON body
- SQLite via SQLAlchemy
- Eligibility ≥80%, calculated live via query, never stored; `excused` counts as attended (`status in ('present','excused')`)
- Flask app factory pattern (`create_app()` in `app.py`) + **4 blueprints now**: `auth`, `attendance`, `api`, **`admin`** (new); `extensions.py` holds `db` separately (circular-import prevention)
- State-changing actions use POST, not GET
- **NEW — Role-based access**: `Lecturer.is_admin` boolean flag distinguishes admin accounts from regular lecturer accounts. Session stores `is_admin` at login time to drive the "Admin Panel" nav link visibility.
- **NEW — Production data strategy (decided this session)**:
  - Timetable entry → **manual Python script** (`insert_timetable.py`, not yet built)
  - Production DB seeding → **Option 1: clean DB + exactly one Admin/Lecturer account**, created via `init_db.py`. No dummy/fake data goes to production.
  - New Student enrollment + new Lecturer accounts → **Admin Panel UI** (self-service, no manual DB scripts needed going forward)

---

## 🗄️ Database Schema (finalized, one addition)
7 tables: `students`, `lecturers`, `subjects`, `enrollments`, `timetable`, `lecture_sessions`, `attendance_records`.

- `Lecturer`: **added `is_admin` (Boolean, default False)** this session.
- `AttendanceRecord`: `record_id`, `session_id`, `student_id`, `status` (present/absent/excused), `marked_time`, `excuse_reason` (medical/sport/other), `updated_by`, `updated_at`.
- `Student.fingerprint_id`: nullable — students can now be created via Admin Panel *before* hardware enrollment happens; field gets filled in later.

Full DDL in `schema.sql`/`models.py`. `config.py` → `SQLALCHEMY_DATABASE_URI = sqlite:///{BASE_DIR}/database/attendance.db` → matches `.gitignore`'s `database/*.db` rule → production DB is git-safe.

---

## ✅ Files/Code Produced — Admin Panel Session (downloaded, ready to place in repo)

| File | Status | Notes |
|---|---|---|
| `models.py` | **Modified** | Added `Lecturer.is_admin` column |
| `app.py` | **Modified** | Registers new `admin_bp` at `/admin` prefix |
| `routes/auth.py` | **Modified** | Login now stores `session["is_admin"]` |
| `routes/admin.py` | **New** | `login_required` + `admin_required` decorators; routes: `/admin/dashboard`, `/admin/students`, `/admin/add_student` (GET/POST, includes subject-enrollment checkboxes), `/admin/lecturers`, `/admin/add_lecturer` (GET/POST, optional "grant admin" checkbox) |
| `templates/base.html` | **Modified** | "Admin Panel" nav link shown only when `session.is_admin` is true |
| `templates/admin_dashboard.html` | **New** | Overview cards (student/lecturer/subject counts, fingerprint-pending count) + quick links |
| `templates/admin_add_student.html` | **New** | Student ID, name, optional fingerprint_id, subject enrollment checkboxes |
| `templates/admin_add_lecturer.html` | **New** | Username, password, full name, optional "grant admin" checkbox |
| `templates/admin_students.html` | **New** | List view with fingerprint-enrollment status pill |
| `templates/admin_lecturers.html` | **New** | List view with Admin/Lecturer role pill |
| `init_db.py` | **New** | Repo-root script: `db.create_all()` on a clean DB + interactive prompt to create the single production Admin account. Safe to re-run (skips if `admin` username already exists) |

All admin templates use **scoped `<style>` blocks** (established pattern) rather than global `style.css` classes — not yet cross-checked against the actual design tokens (`--color-primary`, `.btn`, `.data-table`, `.badge`, etc.) that were shared this session. **Optional future cleanup**: restyle admin templates to reuse those classes for full visual consistency with the rest of the app.

✅ Confirmed working: user tested locally, Admin Panel functioning as expected.

⚠️ **Known migration note**: `db.create_all()` does not alter existing tables. Any existing dev `database/attendance.db` created before this session needs to be deleted and recreated (or manually migrated) to pick up the new `is_admin` column.

---

## 📂 Confirmed unchanged/already in repo
`extensions.py`, `routes/attendance.py` (dashboard, start_session, session_view, report_subjects, report, student_history, update_attendance), `routes/api.py`, `requirements.txt`, `.env.example`, `.gitignore`, `firmware/` placeholder, `seed_data.py` (dev-only now — **not used for production**, superseded by `init_db.py` + Admin Panel for prod data), `report.html`, `report_subjects.html`, `student_history.html`, `dashboard.html`, `session.html` (print feature), `attendance_update.html`, `static/css/style.css` (full design token system — Space Grotesk/Inter/JetBrains Mono, color tokens, `.btn`/`.data-table`/`.badge`/print stylesheet — confirmed this session).

---

## 🚀 Deployment (guide given, not yet executed)
Platform: **PythonAnywhere free tier** (chosen over Render — ephemeral filesystem — and Railway — no longer free).

Guide covers: signup → git clone via Bash console → virtualenv + `pip install -r requirements.txt` → **run `init_db.py`** (create admin account) → Web tab "Add a new web app" → Manual configuration → source/working-directory/virtualenv paths → static files mapping (`/static/` → `.../static`) → WSGI file edit (`from app import create_app; application = create_app()`) → real `.env` from `.env.example` with strong `SECRET_KEY` → Reload → test live URL → future updates via `git pull` + Reload.

---

## 🚧 Current Blocking Issue
None. Admin Panel tested and working locally. Deployment itself has not been executed yet — that remains the next concrete action, but is now sequenced *after* the timetable script.

---

## ✅ Immediate Next Steps (in agreed order)
1. ~~Build Admin Panel (Add Student / Add Lecturer + role-based access)~~ **DONE — tested working**
2. **Build `insert_timetable.py`** — manual script to insert subjects/timetable rows (next task, not yet started)
3. Deploy to PythonAnywhere:
   - `git clone` → venv → `pip install -r requirements.txt`
   - Run `init_db.py` → create the one production Admin account
   - Configure Web tab (manual config, WSGI, static mapping, `.env`)
   - Reload → test live URL
4. Full web-app-side testing with real team members (Admin creates lecturer/student accounts, enrolls students in subjects, runs sessions)
5. **(Postponed)** ESP32 `.ino` firmware — ideally including a **fingerprint enrollment mode** that assigns a `fingerprint_id` to an already-Admin-created student record

---

## 📝 Open Questions (unresolved, carried over)
- Should `/student/history` stay open to any logged-in lecturer, or be restricted to lecturers who teach that specific student? (current behavior: open, intentional but not fully confirmed by user)
- (Optional/low-priority) Add "Update" links to `report.html`/`student_history.html` rows too, matching `session.html`
- (Optional/low-priority) Restyle Admin Panel templates to use `style.css` design tokens instead of scoped inline styles, for full visual consistency

---

## ⚙️ User Preferences (apply throughout)
- Respond in Sinhala by default; technical terms in English (inline/brackets)
- University-level explanations
- Full code files → always create as actual downloadable files, not inline (except <20-line snippets)
- Terminal commands as simple numbered steps
- `"/handoff"` keyword → produce a structured handoff summary of the entire conversation