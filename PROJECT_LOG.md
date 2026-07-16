# PROJECT_LOG.md

මෙම file එක, future chat sessions වලදී AI agent කෙනෙකුට (හෝ ඔයාටම පසුව) project එකේ current context එක ඉක්මනින් තේරුම් ගැනීමට උදව් වන running log එකකි. සෑම major decision/step එකකින් පසුම මෙය update කරන්න.

---

## 🎯 Original Goal

Fingerprint sensor (R307S) + ESP32 based Student Attendance Management System එකක්, Flask web app + SQLite database සමඟ. Lecturer login → today's lectures → session start/live attendance → printable reports → student monthly history (eligibility ≥80%) → false-absent correction + excuse handling → Admin Panel (student/lecturer/subject onboarding).

**GitHub:** https://github.com/didulah/mini_project (user: didulah)
**Live site:** https://himasara.pythonanywhere.com (PythonAnywhere Free tier)

## 🧩 Hardware (Confirmed - built & in hand)

- Fingerprint sensor - R307S
- ESP32 (38 pin)
- RTC Module - DS3231 (HW-084)
- OLED Display 0.91" (4 pin)
- Buzzer + S8050 transistor
- Charging module + 3.7V battery

**Status:** Hardware දැන් ලැබිලා තියෙනවා. Wiring සම්පූර්ණයි, firmware round එකක් test කරලා තියෙනවා (බලන්න පහළ "Hardware Testing Round" කොටස).

## 🏗️ Architecture Decisions

1. **Session-based attendance mapping** — Lecturer login → today's lecture select → "Start Session" කළ පසුව විතරක් ESP32 scans, active session එකට map වේ. "End Session" කළහම status='closed' වී, ඊට පස්සේ scan attempts reject වේ.
2. **Communication:** ESP32 → Flask `/api/scan` (HTTP POST, WiFi, JSON body: `{fingerprint_id, session_id}`) — hardware-agnostic API design
3. **Database:** SQLite (single-file, project scale එකට ප්‍රමාණවත්)
4. **Eligibility rule:** Attendance ≥ 80% → Eligible (excused = attended ලෙස ගණන් ගැනේ). කිසිම විටෙක table එකක store නොවී, query එකකින් live calculate වේ.
5. **Database schema (7 tables):** `students`, `lecturers`, `subjects`, `enrollments`, `timetable`, `lecture_sessions`, `attendance_records`
6. **Timestamps:** UTC වලින් store වේ (`datetime.utcnow()`), display කරන කොට Sri Lanka local time (UTC+5:30) එකට convert වේ (`AttendanceRecord.marked_time_local` property)
7. **Access control:** `/student/history` route එක login වූ සියලුම lecturers ලාට open (Option A - කුඩා trusted team, coordinators/substitutes ලාට broad access ඕන විය හැකි නිසා)
8. **DEMO_MODE (firmware):** එක physical ESP32 device එකක් permanently එක timetable_id එකකට tie වෙන්න ඕන (production behavior) — ඒත් team testing අතරතුර, re-flash නොකර device එකම subjects කිහිපයක් test කරන්න `DEMO_MODE` flag එකක් තියෙනවා (active session එක system-wide follow කරනවා). **Final submission එකට කලින් `DEMO_MODE = false` කරලා, real classroom deployment එකකට `TIMETABLE_ID` reconfirm කරන්න ඕන.**
9. **Enrollment model (NEW - මේ session එකේ වෙනස් කළා):** සිසුවෙකු enroll කරන කොට subject select කරන්න ඕන නෑ — student add උනාම **automatic ව system එකේ ඉන්න සියලුම subjects වලටම** enroll වේ. අලුත් subject එකක් `insert_timetable.py` එකෙන් add උනාම, දැනටමත් ඉන්න students ලාත් auto-enroll වේ (`sync_all_enrollments()` helper function එක හරහා - `models.py` එකේ).

## 📂 Files/Code Produced So Far

| File/Area | Status | Notes |
|---|---|---|
| README.md, schema.sql | ✅ | Project overview + 7-table schema (tested & valid) |
| Flask skeleton (`app.py`, `config.py`, `extensions.py`, `models.py`, `routes/`, `templates/`, `static/`) | ✅ Deployed | App factory pattern + blueprints: `auth`, `attendance`, `api`, `admin` |
| Admin Panel | ✅ Complete | `Lecturer.is_admin` flag, routes for students/lecturers list+add, `admin_required` decorator, `init_db.py` for clean DB init |
| Core attendance routes | ✅ | Session start/end, live attendance (5s auto-refresh), printable reports, student monthly history, false-absent correction + excuse audit trail |
| ESP32 firmware | ✅ Flashed & tested | `firmware/main.ino` — WiFi, session polling via `/api/active_session`, fingerprint scan → JSON POST `/api/scan`, OLED + buzzer feedback, DEMO_MODE support |
| `admin.py` — `/admin/assign_fingerprint` | ✅ | Attach hardware fingerprint template ID to existing student record |
| **Enrollment model change (this session)** | ✅ | `models.py` → `sync_all_enrollments()` added. `admin.py` `add_student` route → subject-selection UI/logic removed, auto-enrolls into all subjects after commit. `admin_add_student.html` → subject checklist removed. `insert_timetable.py` → auto-calls `sync_all_enrollments()` at the end. New file: `backfill_enrollments.py` (one-off migration script for existing data) |
| style.css | ✅ | Design tokens, Space Grotesk/Inter/JetBrains Mono fonts, print stylesheet. Admin templates not yet restyled to match (cosmetic, deferred) |

## 🚧 Current Blocking Issue / Open Verification

Enrollment model change එක (subject auto-enroll) files 4ක් (`models.py`, `admin.py`, `admin_add_student.html`, `insert_timetable.py`) දැනට **local/chat එකේ generate කරලා** තියෙන්නේ — server එකට තවම push/pull/reload වෙලා නෑ. `backfill_enrollments.py` server එකේ run කරලත් නෑ.

## ✅ Immediate Next Steps

1. `models.py`, `admin.py`, `admin_add_student.html`, `insert_timetable.py` — VSCode → commit + push
2. PythonAnywhere Bash console: `workon mini_project_env` → `cd ~/mini_project` → `git pull`
3. `python backfill_enrollments.py` run කර, existing students ලා subjects සියල්ලටම enroll වෙනවාද confirm කරන්න
4. Web tab → Reload
5. Admin Panel එකෙන් student add කරලා, auto-enrollment වැඩ කරනවාද manually verify කරන්න
6. `insert_timetable.py` දිගටම run කරමින් subject අලුතක් add කරලා, existing student ලා auto-enroll වෙනවාද verify කරන්න
7. Team testing දිගටම කරගෙන යාම (Kalana ගේ timetable entries, non-admin lecturer login demo, real student fingerprint enrollment)
8. Submission එකට කලින්: `DEMO_MODE = false`, `TIMETABLE_ID` per-device reconfirm

## 📝 Open Questions (carried over, unresolved)

- (Optional, cosmetic) Admin Panel templates → `style.css` design tokens වලට restyle කිරීම
- Timetable entries list කරන admin UI page එකක් add කරනවාද (දැනට raw `sqlite3` query එකකින් විතරයි බලන්නේ)
- `status=closed` සඳහා `style.css` එකේ CSS styling තියෙනවද (status pill unstyled වෙන්න පුලුවන් - check කරලා නෑ)

## 🖥️ Common Terminal Commands

**App එක run කිරීම (local):**
```
python app.py
```

**GitHub එකට push කිරීම:**
```
git add .
git commit -m "meaningful message about what changed"
git push
```

**PythonAnywhere server එකේ pull + reload:**
```
workon mini_project_env
cd ~/mini_project
git pull
```
(ඊට පස්සේ Web tab → Reload button එක click කරන්න)

**Schema වෙනස් උනොත් DB rebuild:**
```
python init_db.py
python insert_timetable.py
```

---

*Last updated: Enrollment model change - subject auto-enroll (July 2026)*