"""
init_db.py
----------
Production database initializer.

Creates a CLEAN database (all tables, zero fake data) and inserts exactly
ONE Admin/Lecturer account so you can log in for the first time and use
the Admin Panel to add real students, real lecturers, and (via
insert_timetable.py) the timetable.

Usage (run once, on the server, after cloning the repo):
    python init_db.py

Safe to re-run: if the admin account already exists, it will NOT be
duplicated - the script just reports that it's already there.
"""
import getpass

from app import create_app
from extensions import db
from models import Lecturer


def main():
    app = create_app()

    with app.app_context():
        db.create_all()
        print("[OK] All tables created (or already existed).")

        existing = Lecturer.query.filter_by(username="admin").first()
        if existing:
            print("[SKIP] An account with username 'admin' already exists. Nothing to do.")
            return

        print("\nNo admin account found. Let's create the first one.")
        username = input("Admin username [admin]: ").strip() or "admin"
        full_name = input("Admin full name [System Admin]: ").strip() or "System Admin"

        while True:
            password = getpass.getpass("Admin password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password and password == confirm:
                break
            print("Passwords did not match or were empty - try again.")

        admin = Lecturer(username=username, full_name=full_name, is_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        print(f"\n[OK] Admin account '{username}' created successfully.")
        print("You can now log in and use the Admin Panel to add students, lecturers, and enrollments.")


if __name__ == "__main__":
    main()