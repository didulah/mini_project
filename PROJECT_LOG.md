# PROJECT_LOG.md
Fingerprint-Based Student Attendance Management System
Last updated: 2026-07-19

---

## Current branch: `branch2`
`main` = last known-good production state (unified ATTENDANCE + ENROLLMENT firmware,
admin panel, live attendance, reports, false-absent correction, DEMO_MODE flag).
`branch2` = active feature work, **not yet merged to main**.

---

## What's being built on branch2

### 1. Fingerprint DELETE flow
Mirrors the existing ENROLLMENT flow. New `DeviceState` mode `"DELETE"`.

- **models.py**: `DeviceState` got 3 new columns - `delete_student_id`,
  `delete_status`, `delete_message` (mirrors the existing `enroll_*` columns).
- **routes/admin.py**: new routes `start_delete_fingerprint/<student_id>` and
  `cancel_delete_fingerprint`. `assign_fingerprint()` now also queries
  students WITH a fingerprint (`enrolled_students`) to list them for deletion.
- **routes/api.py**: new `/api/delete_result` endpoint (mirrors
  `/api/enroll_result`) - on success, clears `student.fingerprint_id`.
- **templates/admin_assign_fingerprint.html**: new "Students With a
  Fingerprint - Remove Fingerprint" table + DELETE-mode status card +
  auto-refresh (same full-page-reload pattern used for enrollment).
- **firmware/main.ino**: new `runDeleteFlow()` - calls
  `finger.deleteModel(id)` on the sensor, then POSTs `/api/delete_result`.

**Status: web-only test in progress. Hardware not yet tested.**

### 2. Fingerprint ID collision fix
Previously the ESP32 computed the next template ID itself via
`finger.getTemplateCount() + 1` - this breaks once a fingerprint is deleted
from the middle of the sequence (ID gets reused/collides).

**Fix:** ID assignment moved to the server. `/api/poll` (see below) now
computes the lowest unused `fingerprint_id` via a DB query and sends it as
`enroll_fingerprint_id` in the ENROLLMENT response. The device stores the
template under that server-given ID instead of calculating its own.

### 3. Poll endpoint merge (scan delay fix)
**Diagnosed cause of the ~6s scan delay:** every poll cycle the ESP32 was
making TWO sequential blocking HTTPS calls (`/api/device_mode` +
`/api/active_session`), each a full TLS handshake against PythonAnywhere's
free tier - several seconds of blocking time per cycle, during which the
sensor wasn't being read.

**Fix:** merged into a single `GET /api/poll` endpoint returning mode +
session/enroll/delete data in one response. Old `/api/device_mode` and
`/api/active_session` endpoints kept (unused by firmware now, harmless for
manual testing).

**Status: not yet hardware-verified with a stopwatch comparison.**

---

## Known issues / blockers

### `init_db.py` admin-existence check bug (CONFIRMED, not yet fixed)
Running `python init_db.py` on the PythonAnywhere production DB (which
already has an admin account `DidulaAdmin`) threw:
```
sqlite3.IntegrityError: UNIQUE constraint failed: lecturers.username
```
The script's "no admin found -> create one" check is misfiring and trying
to insert a duplicate admin even though one already exists. **The bug
itself has not been located/fixed in the script yet.**

**Workaround used instead (safe, no data loss):** targeted `ALTER TABLE`
via sqlite3 shell after a file-copy backup, instead of running
`init_db.py` against a populated DB:
```sql
ALTER TABLE device_state ADD COLUMN delete_student_id INTEGER;
ALTER TABLE device_state ADD COLUMN delete_status VARCHAR(20) DEFAULT 'idle';
ALTER TABLE device_state ADD COLUMN delete_message VARCHAR(255);
```
This is now the standard approach for any future schema change against a
DB that already has real data - `init_db.py` / full rebuild is only safe
against an EMPTY or throwaway DB.

### Web-only DELETE mode test - unresolved
A `/api/poll` check (browser GET, no hardware) returned
`{"mode": "ATTENDANCE", "session_id": 10}` instead of the expected
`DELETE` mode, right after clicking "Remove Fingerprint" for a test
student. **Root cause not yet confirmed** - most likely explanation:
the clicked student had `fingerprint_id IS NULL`, so
`start_delete_fingerprint()` silently no-ops (flashes a warning and
redirects without changing `DeviceState.mode`). Needs to be re-tested
with a student who has a confirmed non-null `fingerprint_id`, and the
flash message on that attempt needs to be read to confirm.

---

## Recently completed (this session, outside branch2)

- Diagnosed `insert_timetable.py` dedup key precisely:
  `subject_id + lecturer_id + day_of_week + start_time` only -
  changing `end_time` alone on an existing row is silently skipped,
  not updated. Documented as a standing gotcha.
- Walked through adding a new timetable slot end-to-end (edit
  `SUBJECTS` / `TIMETABLE` lists locally -> commit -> push -> pull on
  PythonAnywhere -> `python insert_timetable.py` -> Reload).

---

## Immediate next steps

1. Re-test DELETE mode web-only with a student that definitely has a
   non-null `fingerprint_id`; read the flash message; confirm
   `device_state.mode` actually flips via `sqlite3 ... SELECT mode,
   delete_student_id, delete_status FROM device_state WHERE id=1;`
2. Cancel any DELETE mode left stuck from testing
   (`cancel_delete_fingerprint`) before moving on.
3. Full hardware end-to-end test on branch2:
   - Delete flow (sensor + DB)
   - Enroll -> delete -> re-enroll -> confirm ID reuse has no collision
   - Scan delay: stopwatch comparison, old vs merged `/api/poll`
4. Fix the `init_db.py` admin-existence check bug (not yet located -
   need to view the actual script to diagnose).
5. Once hardware tests pass: merge `branch2` -> `main` (GitHub +
   PythonAnywhere `git pull` + Reload).
6. Continue project report/documentation.

---

## Reference - key file locations
- `models.py` - SQLAlchemy models (`Student`, `Lecturer`, `Subject`,
  `Enrollment`, `Timetable`, `LectureSession`, `AttendanceRecord`,
  `DeviceState`)
- `routes/api.py` - ESP32-facing endpoints (`/scan`, `/api/poll`,
  `/enroll_result`, `/delete_result`, legacy `/device_mode` +
  `/active_session`)
- `routes/admin.py` - Admin Panel routes (students, lecturers,
  fingerprint assign/enroll/delete)
- `templates/admin_assign_fingerprint.html` - enrollment + delete UI
- `firmware/main.ino` - unified ESP32 sketch (ATTENDANCE /
  ENROLLMENT / DELETE modes, merged `/api/poll`)
- `insert_timetable.py` - repo-root script for subjects/timetable
  (idempotent, run locally-edited-then-pushed, never edited on server)