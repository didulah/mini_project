# Fingerprint-based Student Attendance Management System

A project that uses a fingerprint sensor and an ESP32 microcontroller to automatically record student attendance, integrated with a Flask web application. It combines an Embedded System with a Web Application.

🔗 **Live Demo:** [himasara.pythonanywhere.com](https://himasara.pythonanywhere.com)
📂 **Repository:** [github.com/didulah/mini_project](https://github.com/didulah/mini_project)

## 📌 Why this project (Motivation)

This project aims to solve the problems associated with traditional attendance marking methods (paper registers and roll calls):

- Eliminate **proxy attendance (buddy punching)**
- Reduce the lecture time spent on marking attendance
- Eliminate manual data entry errors
- Maintain centralized and searchable historical attendance records
- Automatically calculate attendance percentages (80% eligibility rule)

## 🛠️ Hardware Components

| Component                      | Purpose                                                     |
| ------------------------------- | ------------------------------------------------------------ |
| Fingerprint Sensor - R307S      | Capture students' fingerprints                                |
| ESP32 (38 pin)                  | Main controller for handling the sensor, display, and Wi-Fi   |
| RTC Module - DS3231 (HW-084)    | Provide accurate timestamps                                   |
| OLED Display 0.91" (4 pin)      | Display system status and user feedback                       |
| Buzzer                          | Provide audio confirmation                                    |
| S8050 Transistor                | Drive the buzzer and other components                         |
| Charging Module + 3.7V Battery  | Portable power supply                                          |

> **Status:** Physical hardware wiring not finalized yet. Firmware code is written and ready, but placeholder values (WiFi credentials, server hostname, timetable ID, GPIO pins) must be confirmed against the actual wiring before flashing.

## 💻 Software Stack

- **Backend:** Flask (Python), App Factory pattern with Blueprints
- **Database:** SQLite (SQLAlchemy ORM)
- **Frontend:** HTML/CSS/JS (Flask templates - Jinja2), custom design system (`style.css`)
- **Firmware:** Arduino/C++ (ESP32)
- **Deployment:** PythonAnywhere

## ✨ Core Features

- [x] Lecturer login (username/password)
- [x] Lecturer - Select the current day's lecture and start the attendance session
- [x] Live attendance view during an active session
- [x] Attendance report for all students with printable export
- [x] Student ID-based historical attendance report (monthly)
  - Total lectures held, number of absences, attendance for a specific day, attendance percentage, and eligibility status (≥80% = eligible)
- [x] Update Attendance - Correct false absences (with audit trail)
- [x] Update Attendance - Re-mark attendance for approved excuses (medical, sports, or other reasons)
- [x] Admin Panel - manage students and lecturers (`is_admin` role, dedicated routes/templates)
- [x] `/api/scan` endpoint - hardware-agnostic JSON POST from ESP32 (`fingerprint_id`, `session_id`)
- [x] `/api/active_session` endpoint - lets ESP32 discover the currently active session for its timetable
- [x] `/admin/assign_fingerprint` - attach fingerprint template IDs to student records
- [x] ESP32 firmware (`firmware/main.ino`) - WiFi connection, session polling, fingerprint scan, JSON POST, OLED + buzzer feedback
- [x] Deployment on PythonAnywhere
- [ ] Physical hardware wiring, flashing, and end-to-end hardware test
- [ ] Real fingerprint enrollment for all team members
- [ ] Full team demo (lecturer login + live scan + report generation)

## 📁 Project Structure

```
mini_project/
├── app.py                  # Flask app factory entry point
├── config.py                # Configuration (absolute DB path, etc.)
├── extensions.py             # Shared extensions (db, etc.)
├── models.py                 # SQLAlchemy models (7 tables)
├── schema.sql                 # Database schema reference
├── requirements.txt
├── init_db.py                 # Clean DB initialization script
├── insert_timetable.py         # Insert-only script for subjects/timetable
├── routes/
│   ├── auth.py                 # Login blueprint
│   ├── attendance.py            # Session start, live view, reports, history
│   ├── api.py                    # /api/scan, /api/active_session
│   └── admin.py                   # Admin panel + assign_fingerprint
├── templates/                 # Jinja2 HTML templates
├── static/css/
│   └── style.css                # Design tokens, fonts, components, print styles
├── firmware/
│   └── main.ino                 # ESP32 Arduino sketch
├── database/                   # SQLite DB file (gitignored on production)
├── .env.example
├── PROJECT_LOG.md              # Running development log
└── README.md
```

## 🗄️ Database Schema (7 tables)

`students`, `lecturers`, `subjects`, `enrollments`, `timetable`, `lecture_sessions`, `attendance_records`

## 🚀 Setup

```bash
git clone https://github.com/didulah/mini_project.git
cd mini_project
pip install -r requirements.txt
python init_db.py
python insert_timetable.py
python app.py
```

> ⚠️ **Note:** `db.create_all()` does not alter existing tables. Any schema change requires rebuilding the database via `init_db.py` + `insert_timetable.py`.

## 🌐 Deployment

Deployed on **PythonAnywhere** (free tier):
- WSGI entry point: `from app import create_app; application = create_app()`
- SQLite database persists safely between deployments (unlike ephemeral hosts)
- Workflow: **VSCode → GitHub → `git pull` on PythonAnywhere → Reload Web App**

## 👤 Author

Repo: <https://github.com/didulah/mini_project.git>