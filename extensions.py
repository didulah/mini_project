"""
Flask extension instances live here so both app.py and models.py
can import `db` without circular-import problems.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
