# PROJECT_LOG.md

මෙම file එක, future chat sessions වලදී AI agent කෙනෙකුට (හෝ ඔයාටම පසුව) project එකේ current context එක ඉක්මනින් තේරුම් ගැනීමට උදව් වන running log එකකි. සෑම major decision/step එකකින් පසුම මෙය update කරන්න.

---

## 🎯 Original Goal

Fingerprint sensor (R307S) + ESP32 based Student Attendance System එකක්, Flask web app + SQLite database සමඟ. Lecturers ට login වී, today's lecture select කර, session start කර, live attendance track/report/update කළ හැකි web application එකක්.

- **GitHub:** https://github.com/didulah/mini_project (user: didulah)
- **Live Deploy:** https://himasara.pythonanywhere.com (PythonAnywhere, user: Himasara)

## 🧩 Hardware (built)

- Fingerprint sensor - R307S
- ESP32 (38 pin)
- RTC Module - DS3231 (HW-084)
- OLED Display 0.91" (4 pin)
- Buzzer + S8050 transistor
- Charging module + 3.7V battery

## 🏗️ Architecture Decisions

1. **Session-based attendance mapping** — Lecturer login → today's lecture select → "Start Session" → active session එකකට විතරයි ESP32 scans map වෙන්නේ.
2. **Database:** SQLite, 7 tables — `students`, `lecturers`, `subjects`, `enrollments`, `timetable`, `lecture_sessions`, `attendance_records`. Attendance % කිසිම විටෙක store කරන්නේ නෑ - dynamic calculation.
3. **Eligibility rule:** Attendance ≥ 80% → Eligible
4. **Timestamps:** UTC ලෙස store කරලා, display කරද්දී විතරක් Sri Lanka local time (UTC+5:30) එකට convert කරනවා (`marked_time_local` property).
5. **App structure:** App Factory pattern + Blueprints (`auth`, `attendance`, `api`, `admin`)
6. **Enrollment-in-subjects model (changed):** Students subject select කරන්නේ නෑ - `sync_all_enrollments()` හරහා හැම student කෙනෙක්ම හැම subject එකකටම auto-enroll වෙනවා (student add කරාම සහ subject add කරාම දෙපැත්තෙන්ම trigger වෙනවා).
7. **Admin Panel:** `Lecturer.is_admin` flag, `admin_required` decorator, students/lecturers manage කිරීමට routes.
8. **Access control:** `/student/history` සියලුම logged-in lecturers ලාට open (Option A - small trusted team).
9. **NEW - Unified Fingerprint Enrollment/Attendance firmware (this session):** කලින් enrollment සහ attendance සඳහා වෙනම Arduino sketches දෙකක් තිබුනා (sketch මාරු කරන්න ඕන වීම inconvenient). දැන් **එකම `main.ino`** එකක් — `DeviceState` (singleton DB row) හරහා mode track කරනවා (`ATTENDANCE` / `ENROLLMENT`), Admin Panel එකේ button එකකින් mode switch කරනවා.

## 📡 API Endpoints (current)

| Endpoint | Method | Purpose | Status |
|---|---|---|---|
| `/api/scan` | POST | `{fingerprint_id, session_id}` → attendance mark කරනවා | ✅ unchanged since original design |
| `/api/active_session` | GET | `?timetable_id=X` (optional, DEMO_MODE) → active session ID | ✅ unchanged |
| `/api/device_mode` | GET | Device එකේ current mode (ATTENDANCE/ENROLLMENT) + enrollment student info | ✅ NEW |
| `/api/enroll_result` | POST | Device එකෙන් enrollment success/fail result save කරනවා, mode auto-ව ATTENDANCE එකට switch කරනවා | ✅ NEW |

## 📂 Files/Code Produced So Far

| File | Status | Notes |
|---|---|---|
| `schema.sql` | ✅ | 7 tables |
| `models.py` | ✅ | + `DeviceState` model (singleton, mode tracking), `sync_all_enrollments()` |
| `app.py`, `config.py`, `extensions.py` | ✅ | App factory, deployed |
| `routes/auth.py` | ✅ | Login |
| `routes/attendance.py` | ✅ | Session start, live view, reports, student history |
| `routes/api.py` | ✅ | `/scan`, `/active_session` (unchanged) + `/device_mode`, `/enroll_result` (new) |
| `routes/admin.py` | ✅ | Student/lecturer management + `start_enrollment`, `cancel_enrollment`, `enrollment_status` (new) |
| `templates/admin_assign_fingerprint.html` | ✅ | "Start Enrollment" button, live device status, **auto full-page-refresh while ENROLLMENT mode** (simplified from JS fetch-polling to server-rendered conditional `setTimeout(reload)`) |
| `firmware/main.ino` | ✅ | UNIFIED sketch - ATTENDANCE flow byte-for-byte unchanged from old sketch; adds `pollDeviceMode()` + enrollment routine (`getNextFreeTemplateId()`, `enrollFingerprintAtId()`, `reportEnrollResult()`) |
| `style.css` | ✅ | Design tokens, Space Grotesk/Inter/JetBrains Mono fonts |
| `README.md` | ⚠️ Updated locally, **not yet pushed** — GitHub `main` still shows old "Planned" checklist version |

## 🚧 Current Blocking Issue

None blocking. Currently mid-testing on git branch named **`branch`** (not yet merged to `main`):
- 502 error seen once after a PythonAnywhere reload — turned out to be a normal cold-start delay (server log showed clean startup, no exceptions). Site confirmed working after refresh.
- Web-only testing (Start Enrollment → 🟡 waiting → Cancel → 🟢 idle) — **not yet confirmed done** by user as of last message.
- Hardware (ESP32) end-to-end test — **not yet done**, physical device not yet re-flashed with unified `main.ino`.

## ✅ Immediate Next Steps

1. Finish web-only test of enrollment mode switch on `branch` (Start Enrollment → auto-refresh → Cancel/success/fail display)
2. Confirm DB was rebuilt on PythonAnywhere after this session's schema change (`init_db.py` + `insert_timetable.py`) — `device_state` table must exist
3. Flash unified `firmware/main.ino` to the physical ESP32 — confirm/fill placeholders first:
   - `WIFI_SSID` / `WIFI_PASSWORD`
   - `SERVER_HOST` (should already be `himasara.pythonanywhere.com`)
   - `TIMETABLE_ID` (per-device, confirm against real DB row)
   - `DEMO_MODE` (true during team testing, false before real classroom deployment)
   - GPIO pins (`FINGERPRINT_RX_PIN`, `FINGERPRINT_TX_PIN`, `I2C_SDA_PIN`, `I2C_SCL_PIN`, `BUZZER_PIN`) — confirm against actual wiring
4. End-to-end hardware test: real fingerprint enrollment via Admin Panel + attendance scan flow, confirm no regression
5. Merge `branch` → `main` once fully verified (both web-only and hardware tests pass), then `git pull` + reload on PythonAnywhere's `main` checkout
6. Push the locally-updated `README.md` to GitHub (currently only exists as a generated file, never actually committed/pushed)
7. Before final submission: reconfirm `DEMO_MODE = false` and per-device `TIMETABLE_ID`
8. (Cosmetic, optional, deferred) Restyle Admin Panel templates to `style.css` design tokens

## 📝 Open Questions / Notes carried over

- Whether `/admin/enrollment_status` JSON route (built for the earlier fetch-polling approach) should be removed now that the template uses simple server-rendered auto-refresh instead — currently harmless to leave in, just unused by the template
- Whether `status=closed` has CSS styling in `style.css` (not yet checked)

## 🖥️ Common Terminal Commands

**Local run:**
```
python app.py
```

**Push changes to GitHub:**
```
git add .
git commit -m "meaningful message"
git push
```

**On PythonAnywhere (after schema changes):**
```
cd ~/mini_project
git fetch origin
git checkout branch      # or: git checkout main (after merge)
workon mini_project_env
python init_db.py
python insert_timetable.py
```
Then: Web tab → Reload.

**Check PythonAnywhere error logs:**
```
tail -n 50 /var/log/himasara.pythonanywhere.com.error.log
tail -n 50 /var/log/himasara.pythonanywhere.com.server.log
```

**Freeze installed packages:**
```
pip freeze > requirements.txt
```

---

*Last updated: Unified ATTENDANCE/ENROLLMENT firmware + Admin Panel mode-switching UI built and pushed to `branch` (not yet merged to `main`); PythonAnywhere 502 investigated (cold-start, not a real error) (July 2026)*