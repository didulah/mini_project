# PROJECT_LOG.md — Fingerprint Attendance System

## Overview
Fingerprint (R307S + ESP32) based Student Attendance Management System.
Flask web app (SQLite database) lets lecturers log in, start a lecture
session, watch fingerprint scans mark attendance live, view reports, and
look up individual student history. Hardware firmware is postponed;
software is being built first against a test dataset.

GitHub repo: https://github.com/didulah/mini_project

## Architecture
- **Backend:** Flask app factory pattern (`app.py` → `create_app()`),
  3 blueprints: `auth`, `attendance`, `api`
- **Database:** SQLite via SQLAlchemy (`extensions.py` → `db`, models in
  `models.py`, raw DDL mirror in `schema.sql`)
- **Session-based attendance mapping:** lecturer logs in → sees today's
  lectures (`timetable` filtered by `day_of_week` + `lecturer_id`) →
  clicks **Start Session** → a `lecture_sessions` row is created/reused
  for today → only scans posted while that session is active map to it
- **ESP32 integration:** `/api/scan` POST endpoint (JSON: fingerprint_id,
  session_id) — hardware-agnostic, not yet connected to physical device
- **Eligibility rule:** attendance ≥ 80% → Eligible (calculated on the
  fly, never stored)

## Database Schema (schema.sql / models.py — finalized)
7 tables: `students`, `lecturers`, `subjects`, `enrollments`, `timetable`,
`lecture_sessions`, `attendance_records`. See schema.sql for full DDL,
including the eligibility-% query pattern used across the report and
history routes.

## Routes implemented so far

| Route | Method | Purpose |
|---|---|---|
| `/dashboard` | GET | Today's lectures for the logged-in lecturer |
| `/session/start/<timetable_id>` | POST | Creates (or reuses) today's `lecture_sessions` row, redirects to session view |
| `/session/<session_id>` | GET | Live attendance view — enrolled students, default `absent`, updates as `/api/scan` marks `present` |
| `/report` | GET | Lists the lecturer's subjects to pick from |
| `/report/<subject_id>` | GET | Full attendance table for a subject: attended/absent/%/eligibility per student, printable (browser Print → Save as PDF) |
| `/student/history` | GET | Search by `student_id` (+ optional `month`), shows one card per enrolled subject: lectures held, absences, %, eligibility, day-by-day status |

Still TODO (not implemented yet):
- `/attendance/update/<record_id>` — false-absent correction + medical/sport/other excuse flow (flips `absent` → `present`/`excused`)
- Deployment (Render/PythonAnywhere/Railway — not yet decided)
- ESP32 firmware `.ino` code (postponed, `firmware/` folder is a placeholder)

## Frontend / Design
Design token system in `static/css/style.css`:
- **Colors:** steel-blue primary (`#2F4B7C`), teal accent for "present"/success (`#17A398`), warm amber for pending/excused (`#C9822E`), muted red for absent/error (`#B3261E`)
- **Type:** Space Grotesk (headings), Inter (body), JetBrains Mono (IDs/timestamps) — loaded via Google Fonts in `base.html`
- Reusable components: `.btn`, `.badge` (present/absent/excused), `.data-table`, `.lecture-card`, `.session-summary`, `.search-form`, `.subject-report-card`
- Print stylesheet (`@media print`) hides nav/buttons for a clean printable report
- Responsive breakpoint at 560px; `prefers-reduced-motion` respected
- Login form + heading now center-aligned (`.login-form { margin: 60px auto 0; }`, `.content:has(.login-form) h1 { text-align: center; }`)

## Sample/Test Data
`seed_data.py` (idempotent) creates: 1 lecturer (`lecturer1` / `password123`),
1 subject (`ICT3202` — Embedded Systems), 5 students (249001–249005), their
enrollments, and a timetable entry for **today's** day-of-week — so the
login → dashboard → start session flow can be tested end-to-end
immediately after running it.

## Immediate Next Steps
1. **Update Attendance route** (`/attendance/update/<record_id>`) —
   lecturer corrects a false-absent mark, or applies an excuse_reason
   (medical/sport/other) to flip a record to present/excused
2. Deployment platform decision + setup
3. ESP32 `.ino` firmware — connect the physical sensor to `/api/scan`

## Open Questions
- Deployment platform?
- Timetable data: manual entry, or an admin panel?
- Multiple lecturers/subjects — role-based access needed beyond
  "lecturer only sees their own timetable"?
- Should `/student/history` be restricted to lecturers who teach that
  student, or stay open to any logged-in lecturer (current behaviour)?