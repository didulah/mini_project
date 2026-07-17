from datetime import datetime

from flask import Blueprint, request, jsonify

from extensions import db
from models import Student, LectureSession, AttendanceRecord, DeviceState

api_bp = Blueprint("api", __name__)


# ===========================================================================
# EXISTING ATTENDANCE ENDPOINTS - UNCHANGED
# (kept byte-for-byte the same on purpose, so the tested attendance flow
# cannot regress. The unified firmware only calls these when device_mode
# reports "ATTENDANCE".)
# ===========================================================================

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


@api_bp.route("/active_session", methods=["GET"])
def active_session():
    """
    ESP32 polls this periodically to discover whether a lecturer has
    started a session.

    Two modes, controlled by whether ?timetable_id= is sent:

    - PRODUCTION (timetable_id given): device is permanently tied to one
      classroom/subject slot - only an active session for that exact
      timetable_id counts. Safe for multiple devices/classrooms running
      at the same time.
    - DEMO (timetable_id omitted): returns whichever session was started
      most recently, across ALL timetable entries. Convenient for a
      single physical device testing several subjects without re-flashing
      TIMETABLE_ID each time - but NOT safe if two lecturers start
      sessions for different subjects at the same time, since the device
      can only react to one of them.

    Query param: ?timetable_id=X (optional)
    Response: { "session_id": 7 } or { "session_id": null }
    """
    timetable_id = request.args.get("timetable_id", type=int)

    query = LectureSession.query.filter_by(status="active")
    if timetable_id is not None:
        query = query.filter_by(timetable_id=timetable_id)

    lecture_session = query.order_by(LectureSession.started_at.desc()).first()

    return jsonify({"session_id": lecture_session.session_id if lecture_session else None}), 200


# ===========================================================================
# NEW - unified enrollment/attendance mode switching
# ===========================================================================

@api_bp.route("/device_mode", methods=["GET"])
def device_mode():
    """
    ESP32 polls this FIRST on every cycle, before deciding whether to run
    the attendance flow (existing /api/active_session + /api/scan) or the
    enrollment flow.

    Response when idle / attendance:
        { "mode": "ATTENDANCE" }

    Response when an admin has started enrollment for a student:
        { "mode": "ENROLLMENT", "enroll_student_id": 249001, "enroll_name": "Kasun Perera" }
    """
    state = DeviceState.get_singleton()

    if state.mode == "ENROLLMENT" and state.enroll_student_id is not None:
        student = Student.query.get(state.enroll_student_id)
        return jsonify({
            "mode": "ENROLLMENT",
            "enroll_student_id": state.enroll_student_id,
            "enroll_name": student.name if student else None,
        }), 200

    return jsonify({"mode": "ATTENDANCE"}), 200


@api_bp.route("/enroll_result", methods=["POST"])
def enroll_result():
    """
    ESP32 calls this once after attempting a fingerprint enrollment
    (whether it succeeded or failed), so the server can save the
    fingerprint_id and switch the device back to ATTENDANCE mode.

    Expected JSON body:
        { "student_id": 249001, "fingerprint_id": 12, "success": true }
      or on failure:
        { "student_id": 249001, "success": false, "message": "timeout" }
    """
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    fingerprint_id = data.get("fingerprint_id")
    success = bool(data.get("success"))
    message = data.get("message", "")

    state = DeviceState.get_singleton()

    if state.mode != "ENROLLMENT" or state.enroll_student_id != student_id:
        # Stale/duplicate result, or admin already cancelled - ignore safely.
        return jsonify({"error": "No matching enrollment currently in progress"}), 409

    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    if success and fingerprint_id is not None:
        clash = Student.query.filter(
            Student.fingerprint_id == fingerprint_id,
            Student.student_id != student_id,
        ).first()
        if clash:
            state.enroll_status = "failed"
            state.enroll_message = (
                f"fingerprint_id {fingerprint_id} already assigned to "
                f"{clash.name} ({clash.student_id})"
            )
            state.mode = "ATTENDANCE"
            state.enroll_student_id = None
            state.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"error": "fingerprint_id already assigned to another student"}), 409

        student.fingerprint_id = fingerprint_id
        state.enroll_status = "success"
        state.enroll_message = f"Enrolled fingerprint_id={fingerprint_id} for {student.name}"
    else:
        state.enroll_status = "failed"
        state.enroll_message = message or "Enrollment failed on device"

    # Always hand control back to attendance mode once a result comes in -
    # keeps the device from ever getting stuck in ENROLLMENT.
    state.mode = "ATTENDANCE"
    state.enroll_student_id = None
    state.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "Enrollment result recorded"}), 200