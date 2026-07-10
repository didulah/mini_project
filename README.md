# Fingerprint-based Student Attendance Management System

A project that uses a fingerprint sensor and an ESP32 microcontroller to automatically record student attendance, integrated with a Flask web application. It combines an Embedded System with a Web Application.

## 📌 Why this project (Motivation)

This project aims to solve the problems associated with traditional attendance marking methods (paper registers and roll calls):

* Eliminate **proxy attendance (buddy punching)**
* Reduce the lecture time spent on marking attendance
* Eliminate manual data entry errors
* Maintain centralized and searchable historical attendance records
* Automatically calculate attendance percentages (80% eligibility rule)

## 🛠️ Hardware Components

| Component                      | Purpose                                                     |
| ------------------------------ | ----------------------------------------------------------- |
| Fingerprint Sensor - R307S     | Capture students' fingerprints                              |
| ESP32 (38 pin)                 | Main controller for handling the sensor, display, and Wi-Fi |
| RTC Module - DS3231 (HW-084)   | Provide accurate timestamps                                 |
| OLED Display 0.91" (4 pin)     | Display system status and user feedback                     |
| Buzzer                         | Provide audio confirmation                                  |
| S8050 Transistor               | Drive the buzzer and other components                       |
| Charging Module + 3.7V Battery | Portable power supply                                       |

## 💻 Software Stack

* **Backend:** Flask (Python)
* **Database:** SQLite
* **Frontend:** HTML/CSS/JS (Flask templates - Jinja2)
* **Firmware:** Arduino/C++ (ESP32)

## ✨ Core Features (Planned)

* [ ] Lecturer login (username/password)
* [ ] Lecturer - Select the current day's lecture and start the attendance session
* [ ] ESP32 → Flask API - Real-time fingerprint-based attendance marking
* [ ] Attendance report for all students with printable/PDF export
* [ ] Student ID-based historical attendance report (monthly)

  * Total lectures held, number of absences, attendance for a specific day, attendance percentage, and eligibility status (≥80% = eligible)
* [ ] Update Attendance - Correct false absences
* [ ] Update Attendance - Re-mark attendance for late excuses (medical, sports, or other approved reasons)
* [ ] Deployment (hosting plan TBD)

## 📁 Project Structure (Planned)

```text
mini_project/
├── app.py                 # Flask main application
├── models.py              # Database models
├── requirements.txt
├── templates/             # HTML templates
├── static/                # CSS, JS, images
├── database/
│   └── attendance.db
├── firmware/              # ESP32 Arduino code
│   └── main.ino
├── PROJECT_LOG.md
└── README.md
```

## 🚀 Setup (To be completed)

```bash
git clone https://github.com/didulah/mini_project.git
cd mini_project
pip install -r requirements.txt
python app.py
```

## 👤 Author

Repo: [https://github.com/didulah/mini_project.git](https://github.com/didulah/mini_project.git)
