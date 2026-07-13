# Fingerprint Attendance System — Project Log

_Last updated: 2026-07-13_

## 🎯 Project Goal
Fingerprint sensor (R307S) + ESP32 based Student Attendance Management System —
hardware device එක Flask web app (SQLite database) එකකට integrate කරන project එකක්.
Lecturer login → today's lectures → session start/live attendance → printable
reports → student monthly history (eligibility ≥80%) → false-absent correction +
medical/sport/other excuse handling → Admin Panel for student/lecturer/subject
onboarding.

**GitHub repo:** https://github.com/didulah/mini_project (user: didulah)
**Live deployment:** https://himasara.pythonanywhere.com (PythonAnywhere Free tier)

---

## 🏗️ Architecture (finalized, unchanged)
- Flask app factory pattern (`create_app()`) + 4 blueprints: `auth`, `attendance`, `api`, `admin`
- `extensions.py` holds shared `db` instance (avoids circular imports)
- Session-based attendance mapping (lecturer "Start Session" → only then scans map to it)
- `/api/scan` — hardware-agnostic POST endpoint (JSON: `fingerprint_id`, `session_id`)
- Eligibility ≥80%, calculated live via query, never stored; `excused` counts as attended
- Role-based access: `Lecturer.is_admin` boolean; `session["is_admin"]` set at login

## 🗄️ Database Schema (finalized)
7 tables: `students`, `lecturers`, `subjects`, `enrollments`, `timetable`,
`lecture_sessions`, `attendance_records`. Full field list in `models.py`.

---

## ✅ Completed So Far

### Application code
- Full Admin Panel (dashboard, add/list students, add/list lecturers, `admin_required` decorator)
- All core attendance routes (`dashboard`, `start_session`, `session_view`, `report_subjects`,
  `report`, `student_history`, `update_attendance`) — tested working
- `init_db.py` — clean production DB init with interactive admin account creation, safe to re-run
- `insert_timetable.py` — idempotent script for Subjects + Timetable entries
  (`get_or_create`-style duplicate check on subject_code / on subject+lecturer+day+start_time)
- `style.css` design system (Space Grotesk/Inter/JetBrains Mono, `.btn`, `.data-table`,
  `.badge`, print stylesheet) — used by core pages; Admin templates still use scoped
  inline `<style>` blocks (cosmetic-only cleanup, deferred, no functional impact)

### 🚀 Deployment — DONE (PythonAnywhere Free tier)
Live at `himasara.pythonanywhere.com`. Full setup completed:
- Repo cloned, virtualenv `~/.virtualenvs/mini_project_env` (dependencies installed here —
  **not** in a `venv/` folder inside the repo; duplicate `venv/` was created by mistake once
  and deleted — see gotcha below)
- `.env` created with real `SECRET_KEY`; `DATABASE_URL` line **removed** from `.env` so
  `config.py`'s absolute-path default is used (a relative `DATABASE_URL` was a real risk
  found and fixed this session)
- Web tab: Manual configuration, Python 3.10, virtualenv path set, source/working
  directory `/home/Himasara/mini_project`, static mapping `/static/` →
  `.../mini_project/static`, WSGI file wired to `create_app()`
- Production DB initialized via `init_db.py`, admin account created (username: `DidulaAdmin`)
- Timetable seeded via `insert_timetable.py`: 3 subjects (ET001 Engineering Maths,
  ET002 Computer Programming, ET003 Electrical Circuits); `DidulaAdmin` also teaches
  ET001/Monday (admin account intentionally doubles as a lecturer — confirmed, not a bug)

---

## ⚠️ Key Gotchas Hit This Session (don't repeat)

1. **Stale deploy after `git clone`**: cloning only grabs the commit that existed at clone
   time. Local commits made *after* that need an explicit `git pull` on PythonAnywhere —
   this bit us once (Admin Panel commits existed on GitHub but not on the server until
   `git pull` was run manually).
2. **Two virtualenvs got created by accident** (`~/mini_project/venv` via `python -m venv`,
   and `~/.virtualenvs/mini_project_env` via `workon`). The Web tab config points at
   `.virtualenvs/mini_project_env` — **that's the one that must have `pip install -r
   requirements.txt` run in it.** The stray `venv/` folder was deleted.
3. **`db.create_all()` doesn't alter existing tables.** When `models.py` gained
   `Lecturer.is_admin`, the already-existing production `attendance.db` (created before
   that column existed) needed a full delete + `init_db.py` + `insert_timetable.py` rebuild.
   This is a recurring risk on any future schema change — **check `git pull`'s diff for
   `models.py` changes before just reloading**; if the schema changed, rebuild the DB.
4. **`insert_timetable.py` is INSERT-only** — editing only `end_time` (or any single field)
   on an existing row is invisible to the duplicate-check and gets silently skipped, not
   updated. Workaround during dev: delete DB + rebuild. (No production-safe UPDATE path
   built yet — flagged as a possible future addition if this becomes a real need.)

---

## 📋 Standard Workflows (established this session)

**Add a lecturer or student** → Admin Panel UI in the browser. No bash needed.

**Add a subject or timetable entry** →
1. Edit `insert_timetable.py`'s `SUBJECTS`/`TIMETABLE` lists **in local VSCode only**
   (never `nano` directly on the server — avoids merge conflicts)
2. Local: `git add insert_timetable.py && git commit -m "..." && git push origin main`
3. PythonAnywhere Bash: `cd ~/mini_project && git pull && python insert_timetable.py`

**Deploy any code change** →
1. Local: `git add . && git commit -m "..." && git push origin main`
2. PythonAnywhere Bash: `cd ~/mini_project && git pull`
3. **Check the pull diff for `models.py` changes.** If schema changed:
   `rm database/attendance.db && python init_db.py && python insert_timetable.py`
   (recreates admin account + timetable — re-add any lecturers/students lost this way
   via Admin Panel)
4. If `requirements.txt` changed: `pip install -r requirements.txt`
5. Web tab → **Reload** → hard-refresh browser (`Ctrl+Shift+R`) to verify

---

## 🚧 Current Blocking Issue
None. Deployment is live and working with the current (Admin Panel) codebase.

## ✅ Immediate Next Steps
1. **Team testing**: real student enrollment (Admin Panel), fingerprint-ready student
   records, at least one additional lecturer account (`Kalana` already re-added; confirm
   their timetable entries are correct) for the presentation demo
2. Confirm student subject-enrollment flow in Admin Panel's "Add Student" page — **open
   question, not yet verified this session** (does it let you tick subjects at creation
   time, or is enrollment handled separately/not at all yet?)
3. (Postponed) ESP32 `.ino` firmware + hardware fingerprint enrollment mode

## 📝 Open Questions (carried over)
- `/student/history` — open to any logged-in lecturer, or restrict to lecturers who
  teach that specific student? (currently: open to all)
- (Optional, no functional impact) Restyle Admin Panel templates to use `style.css`
  design tokens instead of scoped inline `<style>` blocks

---

## ⚙️ User Preferences (apply throughout)
- Respond in Sinhala by default; technical terms in English (inline/brackets)
- University-level explanations
- Full code files → always create as actual downloadable files, not inline (except <20-line snippets)
- Terminal commands as simple numbered steps
- `"/handoff"` keyword → produce structured handoff summary of entire conversation