# PROJECT_LOG.md

මෙම file එක, future chat sessions වලදී AI agent කෙනෙකුට (හෝ ඔයාටම පසුව) project එකේ current context එක ඉක්මනින් තේරුම් ගැනීමට උදව් වන running log එකකි. සෑම major decision/step එකකින් පසුම මෙය update කරන්න.

---

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
| Flask skeleton (`app.py`, `config.py`, `extensions.py`, `models.py`, `routes/`, `templates/`, `static/`) | ✅ Created, pushed to GitHub, **verified running locally** | App factory pattern + 3 blueprints (`auth`, `attendance`, `api`). User confirmed `python app.py` runs successfully on `http://127.0.0.1:5000` with `pip install -r requirements.txt`. |
| ESP32 firmware | ⚠️ Not yet added to repo | User has working hardware code locally - needs to be copied into `firmware/` folder |

## 🚧 Current Blocking Issue

කිසිවක් නැත. Flask skeleton එක GitHub repo එකට push වෙලා, locally run කර verify කර ඇත (`python app.py` → `http://127.0.0.1:5000` on Windows/VSCode).

## ✅ Immediate Next Steps

1. Existing ESP32 `.ino` firmware code, `firmware/` folder එකට add කර push කිරීම
2. Seed/sample data script එකක් (test lecturer, subject, timetable rows) - login flow test කරන්න
3. Lecturer login flow end-to-end test කිරීම (real DB record එකක් සමඟ)
4. `/session/start/<timetable_id>` route - "start session" logic implement කිරීම
5. ESP32 → Flask `/api/scan` endpoint එක, real hardware සමඟ integrate කිරීම
6. Attendance report + PDF/print export feature
7. Student historical lookup + eligibility calculation logic
8. Update Attendance (false-absent correction + late-excuse) flow
9. Deployment ක්‍රමයක් තෝරාගැනීම (Render/PythonAnywhere/VPS etc.)

## 📝 Open Questions (User input needed)

- Deployment platform කුමක්ද? (Free-tier options: Render, PythonAnywhere, Railway)
- Lecture timetable data එක manually enter කරනවාද, නැත්නම් admin panel එකකින් manage කරනවාද?
- Multiple lecturers/subjects සඳහා role-based access අවශ්‍යද?

## 🖥️ Common Terminal Commands (VSCode)

**App එක run කිරීම (project folder එක ඇතුළේ):**
```
python app.py
```
Stop කරන්න: `CTRL+C`

**අලුත් file/changes GitHub එකට push කිරීම:**
```
git add .
git commit -m "meaningful message about what changed"
git push
```

**Package අලුතක් install කළාට පස්සේ (e.g. requirements.txt එකට එකතු කළොත්):**
```
pip install -r requirements.txt
```

**දැනට install කරලා තියෙන packages list එක `requirements.txt` එකට freeze කිරීම (අලුත් package එකක් install කළහොත්):**
```
pip freeze > requirements.txt
```

---
*Last updated: Flask skeleton pushed to GitHub & verified running (July 2026)*