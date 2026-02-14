from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = 'database.db'

# ─── This function connects to the database ───
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # lets us use column names
    return conn

# ─── This creates the database tables on first run ───
def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id   TEXT PRIMARY KEY,
            student_name TEXT NOT NULL,
            course       TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT NOT NULL,
            date        TEXT NOT NULL,
            time_in     TEXT NOT NULL,
            month       TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'Present'
        )
    ''')
    conn.commit()

    # ─── Add some sample students so you can test right away ───
    sample_students = [
        ('S1001', 'Amal Perera',    'Computer Science'),
        ('S1002', 'Nimal Fernando', 'Information Technology'),
        ('S1003', 'Kamali Silva',   'Software Engineering'),
    ]
    for s in sample_students:
        try:
            conn.execute('INSERT INTO students VALUES (?, ?, ?)', s)
        except:
            pass  # skip if student already exists
    conn.commit()
    conn.close()

# ─── HOME PAGE — search form ───
@app.route('/')
def index():
    return render_template('index.html')

# ─── SEARCH — lecturer submits a student ID ───
@app.route('/search', methods=['POST'])
def search():
    student_id = request.form['student_id'].strip().upper()
    conn = get_db()

    student = conn.execute(
        'SELECT * FROM students WHERE student_id = ?', (student_id,)
    ).fetchone()

    if not student:
        conn.close()
        return render_template('index.html', error=f"No student found with ID: {student_id}")

    records = conn.execute(
        'SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC', (student_id,)
    ).fetchall()

    # ─── Calculate monthly summary ───
    monthly = {}
    for r in records:
        m = r['month']
        if m not in monthly:
            monthly[m] = {'present': 0, 'absent': 0}
        if r['status'] == 'Present':
            monthly[m]['present'] += 1
        else:
            monthly[m]['absent'] += 1

    conn.close()
    return render_template('student.html',
                           student=student,
                           records=records,
                           monthly=monthly)

# ─── ADD ATTENDANCE — called by fingerprint scanner ───
# Example URL: /add_record?student_id=S1001&status=Present
@app.route('/add_record')
def add_record():
    student_id = request.args.get('student_id', '').strip().upper()
    status     = request.args.get('status', 'Present')

    if not student_id:
        return "Error: No student_id provided", 400

    now   = datetime.now()
    date  = now.strftime('%Y-%m-%d')
    time  = now.strftime('%H:%M:%S')
    month = now.strftime('%B %Y')

    conn = get_db()

    # Check student exists
    student = conn.execute(
        'SELECT * FROM students WHERE student_id = ?', (student_id,)
    ).fetchone()

    if not student:
        conn.close()
        return f"Error: Student {student_id} not found", 404

    conn.execute(
        'INSERT INTO attendance (student_id, date, time_in, month, status) VALUES (?, ?, ?, ?, ?)',
        (student_id, date, time, month, status)
    )
    conn.commit()
    conn.close()
    return f"Attendance recorded for {student_id} at {time}", 200

# ─── ADD STUDENT — add a new student to the system ───
@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        sid   = request.form['student_id'].strip().upper()
        name  = request.form['student_name'].strip()
        course= request.form['course'].strip()
        conn  = get_db()
        try:
            conn.execute('INSERT INTO students VALUES (?, ?, ?)', (sid, name, course))
            conn.commit()
            message = f"Student {name} added successfully!"
        except:
            message = f"Error: Student ID {sid} already exists."
        conn.close()
        return render_template('add_student.html', message=message)
    return render_template('add_student.html')

# ─── RUN THE APP ───
if __name__ == '__main__':
    init_db()  # create tables + sample data on startup
    print("Server running! Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)

