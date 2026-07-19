# Fingerprint-Based Student Attendance Management System

A hardware + web application project combining an ESP32-based fingerprint
device with a Flask/SQLite attendance system, built for Wayamba University
of Sri Lanka (Faculty of Technology, ENAC 1X0 module).

- **Live app:** https://himasara.pythonanywhere.com
- **Repo:** https://github.com/didulah/mini_project

---

## What it does

- Students mark attendance by placing a finger on an R307S fingerprint
  sensor connected to an ESP32.
- Lecturers log in to the web app, pick today's lecture from their
  timetable, and start a live attendance session.
- Live attendance view auto-refreshes as students scan in.
- Lecturers can generate printable attendance reports, and look up a
  student's monthly history (lectures held, lectures absent, attendance
  percentage, eligibility at the 80% threshold).
- False-absent corrections and excuse handling (medical / sport / other)
  update past records with a full audit trail.
- Admin Panel: manage students, lecturers, and fingerprint templates
  (enroll and remove, both via live hardware or manual entry).

---

## Hardware

- ESP32 (38-pin devkit)
- R307S fingerprint sensor (UART)
- DS3231 RTC module (I2C)
- 0.91" SSD1306 OLED display (I2C, shares bus with RTC)
- Buzzer (driven via S8050 transistor)
- 3.7V battery + charging module

## Software stack

- **Backend:** Flask (application factory pattern, blueprints: `auth`,
  `attendance`, `api`, `admin`), SQLAlchemy, SQLite
- **Firmware:** Arduino/ESP32 (C++), libraries: `Adafruit_Fingerprint`,
  `Adafruit SSD1306`, `ArduinoJson`, `RTClib`, `WiFiClientSecure`
- **Deployment:** PythonAnywhere (free tier)

---

## Firmware operating modes

A single unified `main.ino` sketch drives the device through three modes,
controlled entirely from the Admin Panel (no re-flashing needed to switch):

| Mode | Trigger | What the device does |
|---|---|---|
| `ATTENDANCE` (default) | idle | Polls for an active session, scans fingerprints, POSTs `/api/scan` |
| `ENROLLMENT` | Admin clicks "Start Enrollment" for a student | Runs a two-scan enrollment routine, stores the template under a **server-assigned** fingerprint ID, POSTs `/api/enroll_result` |
| `DELETE` | Admin clicks "Remove Fingerprint" for a student | Deletes the matching template from the sensor via `finger.deleteModel()`, POSTs `/api/delete_result` |

The device polls a single merged endpoint, `GET /api/poll`, once per cycle
to discover its current mode and any relevant session/enrollment/delete
data - this replaced two separate HTTPS calls to cut ESP32 scan latency.

---

## Project structure (high level)

```
mini_project/
├── app.py                  # Flask app factory
├── extensions.py           # db (SQLAlchemy) instance
├── models.py                # Student, Lecturer, Subject, Enrollment,
│                            # Timetable, LectureSession, AttendanceRecord,
│                            # DeviceState
├── routes/
│   ├── auth.py              # lecturer login/logout
│   ├── attendance.py        # dashboard, session start/end, reports
│   ├── admin.py              # admin panel (students, lecturers, fingerprints)
│   └── api.py                # ESP32-facing endpoints (poll, scan, enroll/delete results)
├── templates/                # Jinja templates
├── static/                   # style.css (design tokens, shared components)
├── firmware/
│   └── main.ino              # unified ESP32 sketch
├── init_db.py                 # create tables + first admin account
├── insert_timetable.py        # idempotent subjects/timetable seeding script
└── database/
    └── attendance.db          # SQLite file (gitignored, persistent on server)
```

---

## Local development workflow

1. Edit code in VSCode.
2. `git push` to a feature branch (e.g. `branch2`) - `main` is always kept
   as the last known-good production state.
3. On PythonAnywhere: `git pull`, then the Web tab's **Reload** button.
4. Never edit files directly on the server.

### Database schema changes
`db.create_all()` does **not** alter existing tables. Any schema change
against a database that already has real data needs a targeted
`ALTER TABLE ...` via the `sqlite3` shell (after taking a file-copy
backup) - **not** a full `init_db.py` re-run, which is only safe against
an empty/throwaway database.

### Timetable changes
Edit the `SUBJECTS` / `TIMETABLE` lists in `insert_timetable.py` locally,
commit, push, then run `python insert_timetable.py` on the server. The
script is idempotent (skips subjects/rows that already exist) but its
duplicate check for timetable rows only considers
`subject + lecturer + day_of_week + start_time` - changing `end_time`
alone on an existing row will be silently skipped, not updated.

---

## Known limitations

- `init_db.py`'s "create first admin if none exists" check currently has
  a bug that can throw a `UNIQUE constraint failed: lecturers.username`
  error if run against a DB that already has an admin account. Fix
  pending - use the manual `ALTER TABLE` approach for schema changes in
  the meantime.
- `DEMO_MODE` in `main.ino` must be set to `false` with a confirmed
  `TIMETABLE_ID` before any real single-classroom deployment.

---

## Status

Core attendance flow (unified ATTENDANCE + ENROLLMENT firmware, admin
panel, live attendance, reports, false-absent correction) is complete and
deployed on `main`. Fingerprint DELETE flow and a scan-delay fix (merged
polling endpoint) are in progress on `branch2`, pending hardware testing
before merge.