from datetime import datetime

from flask import Blueprint, request, jsonify

from extensions import db
from models import Student, LectureSession, AttendanceRecord

api_bp = Blueprint("api", __name__)


@api_bp.route("/scan", methods=["POST"])
def scan():
    """
    ESP32 calls this after it matches a fingerprint against its own
    local R307S template store.

    Expected JSON body:
        { "fingerprint_id": 12, "session_id": 7 }
    """
    data = request.get_json(silent=True) or {}
    fingerprint_id = data.get("fingerprint_id")
    session_id = data.get("session_id")

    if fingerprint_id is None or session_id is None:
        return jsonify({"error": "fingerprint_id and session_id are required"}), 400

    student = Student.query.filter_by(fingerprint_id=fingerprint_id).first()
    if not student:
        return jsonify({"error": "Unknown fingerprint"}), 404

    lecture_session = LectureSession.query.get(session_id)
    if not lecture_session or lecture_session.status != "active":
        return jsonify({"error": "No active session with that ID"}), 400

    record = AttendanceRecord.query.filter_by(
        session_id=session_id, student_id=student.student_id
    ).first()

    if record is None:
        record = AttendanceRecord(session_id=session_id, student_id=student.student_id)
        db.session.add(record)

    record.status = "present"
    record.marked_time = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": f"Attendance marked for {student.name}"}), 200
