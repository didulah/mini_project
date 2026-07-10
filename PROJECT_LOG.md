# PROJECT_LOG.md
## 🎯 Original Goal

Fingerprint sensor + ESP32 based Student Attendance System එකක්, Flask web app + SQLite database සමඟ සම්පූර්ණ කිරීම. Lecturers ට login වී, lecture select කර, attendance track/report/update කළ හැකි web application එකක් සමඟ.

## 🧩 Hardware (Confirmed - already built)

- Fingerprint sensor - R307S
- ESP32 (38 pin)
- RTC Module - DS3231 (HW-084)
- OLED Display 0.91" (4 pin)
- Buzzer + S8050 transistor
- Charging module + 3.7V battery

## 🏗️ Architecture Decisions

1. **Session-based attendance mapping** — Fingerprint sensor එකට "මේක කුමන lecture එකටද" කියලා තනියෙන් දැනගන්න බැරි නිසා, දේශකයා web app එකෙන් login → today's lecture select → "start session" කළ පසුව විතරක් ESP32 එකෙන් එන scans, active session එකට map වේ. (තහවුරු කළ decision - implementation තවම නැත)
2. **Communication:** ESP32 → Flask API (HTTP POST, WiFi) - protocol/endpoint design තවම නැත
3. **Database:** SQLite (single-file, project scale එකට ප්‍රමාණවත්)
4. **Eligibility rule:** Attendance ≥ 80% → Eligible, අඩුනම් Not Eligible
5. **Database schema (finalized):** `students`, `lecturers`, `subjects`, `enrollments`, `timetable`, `lecture_sessions`, `attendance_records` - 7 tables. `timetable` = weekly recurring schedule (lecturer login → today's lectures filter කරන්නේ මෙතනින්), `lecture_sessions` = timetable එකකින් දිනකට generate වෙන actual instance. Attendance % කිසිම විටෙක table එකක store කරන්නේ නෑ - query එකකින් dynamic ලෙස calculate කරනවා. Schema file: `schema.sql` (SQLite, tested & valid).

## 📂 Files/Code Produced So Far

| File | Status | Notes |
|---|---|---|
| README.md | ✅ Created | Project overview, hardware/software list, planned structure |
| PROJECT_LOG.md | ✅ Created | මෙම file එක |
| schema.sql | ✅ Created & tested | 7 tables, indexes, sample eligibility query included |
| app.py | ❌ Not started | |
| ESP32 firmware | ⚠️ Already exists locally (not yet in repo) | User has working hardware code |
| Templates/Frontend | ❌ Not started | |

## 🚧 Current Blocking Issue

කිසිවක් නැත - project එක design/planning stage එකේ පවතී. GitHub repo එක (https://github.com/didulah/mini_project) හිස්ව ඇත.

## ✅ Immediate Next Steps

1. Flask project skeleton (`app.py`, folder structure, `models.py`/SQLAlchemy mapping to schema.sql) සකස් කිරීම
2. Lecturer login + lecture selection flow implement කිරීම
3. ESP32 → Flask API endpoint design සහ existing firmware code සමඟ integrate කිරීම
4. Attendance report + PDF/print export feature
5. Student historical lookup + eligibility calculation logic
6. Update Attendance (false-absent correction + late-excuse) flow
7. Deployment ක්‍රමයක් තෝරාගැනීම (Render/PythonAnywhere/VPS etc.)

## 📝 Open Questions (User input needed)

- Deployment platform කුමක්ද? (Free-tier options: Render, PythonAnywhere, Railway)
- Lecture timetable data එක manually enter කරනවාද, නැත්නම් admin panel එකකින් manage කරනවාද?
- Multiple lecturers/subjects සඳහා role-based access අවශ්‍යද?

---
*Last updated: Initial creation*