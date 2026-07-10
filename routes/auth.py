from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from models import Lecturer

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if "lecturer_id" in session:
        return redirect(url_for("attendance.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        lecturer = Lecturer.query.filter_by(username=username).first()

        if lecturer and lecturer.check_password(password):
            session["lecturer_id"] = lecturer.lecturer_id
            session["lecturer_name"] = lecturer.full_name
            return redirect(url_for("attendance.dashboard"))

        flash("Invalid username or password.")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
