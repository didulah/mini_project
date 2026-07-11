# PROJECT LOG — Fingerprint-based Student Attendance Management System

_Last updated: 2026-07-11_

## 🎯 Project Goal
R307S fingerprint sensor + ESP32 based hardware device එකක් Flask web app
(SQLite database) එකකට සම්බන්ධ කරන Student Attendance Management System.
Lecturer login → today's lectures → session start → live fingerprint-based
attendance → reports (printable) → student-wise monthly history →
false-absent correction / excuse handling.

**Repo**: https://github.com/didulah/mini_project (username: didulah)
**Strategy**: Software-first — web app fully working with seed/test data
before hardware (ESP32 + R307S) integration.

---

## 🏗️ Architecture Decisions

1. **Session-based attendance mapping** — lecturer explicitly "starts" a
   session for today's timetable slot; only fingerprint scans after that
   map to the active `lecture_sessions` row.
2. **`/api/scan` endpoint** — hardware-agnostic, accepts JSON
   (`fingerprint_id`, `session_id`), testable independently of physical
   sensor.
3. **Database**: SQLite via SQLAlchemy, 7 tables (`students`, `lecturers`,
   `subjects`, `enrollments`, `timetable`, `lecture_sessions`,
   `attendance_records`).
4. **Eligibility rule**: attendance ≥ 80% → Eligible — calculated live via
   query at report/history time, **never** stored as a column.
5. **`excused` status counts as attended** for eligibility purposes
   (`status in ('present', 'excused')` — used consistently in
   `report()` and `student_history()`).
6. **Backend structure**: Flask **app factory pattern**
   (`create_app()` in `app.py`) + 3 blueprints (`auth`, `attendance`,
   `api`). `extensions.py` holds the SQLAlchemy `db` instance separately
   to avoid circular imports.
7. State-changing actions (start session, update attendance) use **POST**,
   not GET — avoids accidental triggers.

---

## 🗄️ Database Schema (finalized, unchanged this session)

`AttendanceRecord` key columns: `record_id`, `session_id`, `student_id`,
`status` (`present`/`absent`/`excused`, default `absent`), `marked_time`,
`excuse_reason` (`medical`/`sport`/`other`), `updated_by` (FK → lecturers),
`updated_at`. Unique constraint on `(session_id, student_id)`.

Full DDL: `schema.sql` / `models.py` (repo root).

---

## ✅ Completed So Far

### Backend (`routes/attendance.py`)
- `dashboard()` — today's lectures for the logged-in lecturer
- `start_session()` — `POST /session/start/<timetable_id>`, ownership
  check, duplicate-session prevention (reuses today's session if it
  already exists)
- `session_view()` — `GET /session/<session_id>`, live attendance list,
  auto-creates default-`absent` records for enrolled students
- `report_subjects()` — `GET /report`, subject picker for lecturer's own
  subjects
- `report()` — `GET /report/<subject_id>`, full attendance table with
  attended/absent/%/eligibility, printable
- `student_history()` — `GET /student/history`, search by `student_id` +
  optional `month`, per-subject monthly breakdown with daily status
  (intentionally **not** restricted to the searching lecturer's own
  subjects — treated as a general staff lookup function)
- **`update_attendance()`** — `GET/POST /attendance/update/<record_id>`
  *(NEW this session)* — false-absent correction (flip `absent` →
  `present`) and excuse handling (`medical`/`sport`/`other` →
  `excused`, counts as attended). Sets `marked_time` automatically when
  manually marking present; clears it when reverting to absent. Records
  `updated_by`/`updated_at` for an audit trail. Ownership-checked like
  the other routes (403 if the record doesn't belong to the logged-in
  lecturer's session).

### Templates
- `dashboard.html`, `base.html` (nav, fonts, login centering fix),
  `session.html`, `report_subjects.html`, `report.html`,
  `student_history.html` — from prior sessions
- **`attendance_update.html`** *(NEW)* — radio-button status selector
  (present/excused/absent) with a JS-toggled excuse-reason dropdown,
  self-contained scoped `<style>` block (card layout, stacked radio
  options) since these classes aren't yet in the global `style.css`
- **`session.html` — print feature added** *(NEW)*: "Print / Save as PDF"
  button (`window.print()`), `.no-print` / `.print-only` classes +
  `@media print` rules (scoped inline), "Update" link added per
  student row

### Infrastructure
- `seed_data.py` — idempotent test-data seeder (1 lecturer, 1 subject,
  5 students, enrollments, today's-weekday timetable row)
- `.gitignore` reviewed and **confirmed correct** — `database/*.db` and
  `instance/` are both ignored, so `git pull` on the deployed server
  will not overwrite the production database; `.env` is also ignored
  (SECRET_KEY stays server-side only)

---

## 🚀 Deployment — In Progress

**Platform decision: PythonAnywhere (free tier)**, chosen over Render
(ephemeral filesystem — SQLite wiped on every redeploy/restart, unusable
for this project) and Railway (no longer meaningfully free — persistent
uptime requires the $5/mo Hobby plan).

Full step-by-step guide already given to the user, covering: account
signup → `git clone` via Bash console → virtualenv + `pip install -r
requirements.txt` → seed/init the DB → "Add a new web app" → Manual
configuration → source/working-directory/virtualenv paths → static files
mapping → **WSGI file edit** (must use
`from app import create_app; application = create_app()` since the
project uses the app factory pattern, not the plain
`app = Flask(__name__)` pattern) → `.env` file creation from
`.env.example` with a real `SECRET_KEY` → Reload → test the live URL →
future updates via `git pull` + Reload.

---

## 🚧 Current Blocking / Open Items

1. **Confirm `config.py`'s `SQLALCHEMY_DATABASE_URI`** actually points
   somewhere covered by `.gitignore` (`database/*.db` or `instance/`) —
   not yet verified against the real file, only inferred from the
   `.gitignore` contents.
2. **Step 4 of the deployment guide (production DB init)** — still
   unconfirmed whether to run `seed_data.py` as-is on the production
   server (creates dummy test data: `lecturer1`/`password123`, etc.) or
   write a separate lightweight `init_db.py` that only calls
   `db.create_all()` without seeding fake students/lecturers.
3. Actually **run through the deployment guide** on PythonAnywhere and
   confirm the live site works.

## 📝 Open Questions (carried over, still unresolved)
- Timetable data entry: stays manual (via seed/DB scripts), or gets an
  admin UI?
- Should `/student/history` stay open to any logged-in lecturer, or be
  restricted to lecturers who teach that student? (current behavior:
  open — intentional per earlier discussion, but not fully confirmed)

## ⏭️ Immediate Next Steps
1. Confirm/paste `config.py`'s DB URI line
2. Decide on production DB seeding approach (real seed vs. dummy seed vs.
   empty `init_db.py`)
3. Walk through the PythonAnywhere deployment guide end-to-end; debug via
   the Error log if needed
4. *(Optional, low-priority)* Add "Update" links to `report.html` /
   `student_history.html` rows too, matching `session.html`
5. *(Postponed)* ESP32 `.ino` firmware — connect physical R307S sensor to
   `/api/scan`

---

## ⚙️ User Preferences (apply throughout)
- Respond in Sinhala by default; technical terms in English (inline/brackets)
- University-level explanations
- Full code files → always create as actual downloadable files, not inline
  (except <20 line snippets)
- "/handoff" keyword → produce a structured handoff summary for a new chat