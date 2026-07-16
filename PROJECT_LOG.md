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

## Session update - ESP32 firmware + admin fingerprint assignment (software prep)

**Decisions confirmed:**
- `/student/history` access control: kept as Option A (open to all logged-in
  lecturers) - simplicity + small trusted team, no code change needed.

**New files produced (not yet committed/pulled to server):**
- `firmware/main.ino` - full ESP32 sketch: WiFi connect, polls
  `/api/active_session?timetable_id=X`, reads R307S via
  `Adafruit_Fingerprint`, POSTs to `/api/scan`, OLED + buzzer feedback.
  Config placeholders at top of file: `WIFI_SSID`, `WIFI_PASSWORD`,
  `TIMETABLE_ID`, and GPIO pin numbers (`FINGERPRINT_RX_PIN=16`,
  `FINGERPRINT_TX_PIN=17`, `I2C_SDA_PIN=21`, `I2C_SCL_PIN=22`,
  `BUZZER_PIN=25`).
- `routes/api.py` addition: `GET /api/active_session?timetable_id=X` -
  was referenced in earlier planning but missing from the live codebase;
  added now so firmware has a session-discovery endpoint.
- `routes/admin.py` addition: `GET/POST /admin/assign_fingerprint` -
  lists students with `fingerprint_id IS NULL`, lets admin type in the
  fingerprint template ID captured during R307S enrollment mode and
  attach it to a student record.
- `templates/admin_assign_fingerprint.html` - matching template.
- Full wiring/pin diagram produced (ESP32 <-> R307S, OLED, DS3231, buzzer
  + S8050 transistor, battery + charging module), including a caution
  about confirming R307S TX/RX logic-level voltage against ESP32 GPIO
  (3.3V) before wiring, and a note that OLED + DS3231 safely share the
  same I2C bus (different addresses: 0x3C vs 0x68).

**Not yet done:**
- None of the above files have been committed/pushed/pulled to
  PythonAnywhere yet.
- `main.ino` config placeholders (WiFi credentials, `TIMETABLE_ID`, pin
  numbers) still need real values before flashing.
- `TIMETABLE_ID` lookup method: query production DB directly via
  PythonAnywhere Bash console:
  `sqlite3 database/attendance.db "SELECT * FROM timetable;"`
  (no admin UI page for listing timetable entries yet - optional future
  addition).

**Hardware status:** still not physically in hand. Once available: wire
per the diagram, open `firmware/main.ino` in Arduino IDE (user has this
installed), install libraries (Adafruit Fingerprint Sensor Library,
Adafruit SSD1306, Adafruit GFX, ArduinoJson, RTClib), fill config values,
flash, then enroll a real fingerprint and assign it via
`/admin/assign_fingerprint`.

## Session Update — 2026-07-16 (Hardware testing round)

**Context:** Physical hardware (ESP32 + R307S) now in hand, several students enrolled with real fingerprint templates. First live end-to-end tests run against the deployed app.

### Bugs found & fixed this session

1. **Live Attendance view never updated** — `session.html` had no auto-refresh; page only reflected data from the moment it was first loaded. Fixed with a `setTimeout(() => location.reload(), 5000)` script, active only while `lecture_session.status == 'active'`.
2. **No way to close a session** — `end_session()` route added to `routes/attendance.py` (`POST /session/end/<session_id>`), sets `status='closed'` + `ended_at`. `/api/scan` already rejected scans on closed sessions, so this was the missing piece to stop late/proxy scans after class ends. "End Session" button added to `session.html` (shown only while active, with a JS confirm dialog).
3. **500 Internal Server Error (TemplateSyntaxError)** — caused by a literal `{% if %}` typed inside a JS *comment* in `session.html`. Jinja parses `{% %}` anywhere in the file regardless of context (HTML/JS/comment). Fixed by rewording the comment to avoid literal Jinja syntax.
4. **Root cause of "OLED says success but web shows Absent"** — ESP32 firmware had `TIMETABLE_ID = 1` (an unconfirmed placeholder, never updated from the template default). It was silently marking attendance against a stale `session_id=1`, not the `session_id=7` the lecturer was viewing in-browser. Confirmed via direct SQLite queries on `lecture_sessions` / `attendance_records`. Fixed by setting `TIMETABLE_ID = 7` (the real value for the subject under test) and re-flashing.
5. **6 dangling `active` sessions (session_id 1–6)** found — leftovers from earlier testing rounds, before `end_session()` existed. Manually closed via:
   ```sql
   UPDATE lecture_sessions SET status='closed', ended_at=datetime('now') WHERE session_id IN (1,2,3,4,5,6);
   ```
6. **`marked_time` displayed in UTC, not Sri Lanka local time** — `datetime.utcnow()` is correct for storage, but templates rendered it raw. Added `AttendanceRecord.marked_time_local` property in `models.py` (`SRI_LANKA_OFFSET = timedelta(hours=5, minutes=30)`), and switched `session.html` to use it. (`attendance_update.html` doesn't display `marked_time` at all, so no change needed there.)
7. **Demo-mode fallback added** so the single physical device can test multiple subjects without re-flashing between them:
   - `routes/api.py`: `timetable_id` query param on `/api/active_session` is now **optional**. If given → production behavior (only that exact timetable_id's active session counts). If omitted → returns whichever session is currently active, most-recently-started, across the whole system.
   - `firmware/main.ino`: new `const bool DEMO_MODE` flag. When `true`, ESP32 calls `/api/active_session` without the `timetable_id` param. **Two lecturers must not start sessions for different subjects at the same time while DEMO_MODE is true** — the device can only follow one. Set `DEMO_MODE = false` (and confirm `TIMETABLE_ID`) before any real single-classroom deployment.
8. **Transient PythonAnywhere "Something went wrong :-( / Unhandled Exception"** — resolved by a simple Reload; did not reproduce. Likely a free-tier reload hiccup rather than an app bug, but keep an eye out if it recurs.

### ⚠️ Unverified — check first in next session
Confirm these files are actually **committed, pushed, and pulled** on the PythonAnywhere server (some fixes were only handed over as downloadable files in chat and may not be deployed yet):
- `models.py` (marked_time_local + SRI_LANKA_OFFSET)
- `routes/api.py` (optional timetable_id / demo-mode active_session)
- `routes/attendance.py` (end_session route)
- `templates/session.html` (auto-refresh + End Session button + jinja fix + marked_time_local)
- `firmware/main.ino` (TIMETABLE_ID=7, DEMO_MODE=true) — also re-flash ESP32 if not already done

Run on the server to double check:
```bash
cd ~/mini_project
git log --oneline -5
git status
```