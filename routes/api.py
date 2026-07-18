from datetime import datetime

from flask import Blueprint, request, jsonify

from extensions import db
from models import Student, LectureSession, AttendanceRecord, DeviceState

api_bp = Blueprint("api", __name__)


def _next_free_fingerprint_id():
    """
    Lowest positive integer not currently assigned to any student's
    fingerprint_id. Needed because letting the ESP32 compute
    getTemplateCount()+1 breaks once a fingerprint has been deleted
    from the middle of the sequence (ID collisions).
    """
    used_ids = {
        s.fingerprint_id
        for s in Student.query.filter(Student.fingerprint_id.isnot(None)).all()
    }
    candidate = 1
    while candidate in used_ids:
        candidate += 1
    return candidate


# ===========================================================================
# EXISTING ATTENDANCE ENDPOINTS - UNCHANGED (kept byte-for-byte the same
# on purpose, so the tested attendance flow cannot regress)
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
    Kept for backward compatibility / manual testing (e.g. curl, Postman).
    The firmware no longer calls this directly - see /api/poll below.
    """
    timetable_id = request.args.get("timetable_id", type=int)

    query = LectureSession.query.filter_by(status="active")
    if timetable_id is not None:
        query = query.filter_by(timetable_id=timetable_id)

    lecture_session = query.order_by(LectureSession.started_at.desc()).first()

    return jsonify({"session_id": lecture_session.session_id if lecture_session else None}), 200


@api_bp.route("/device_mode", methods=["GET"])
def device_mode():
    """
    Kept for backward compatibility / manual testing. The firmware no
    longer calls this directly - see /api/poll below.
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


# ===========================================================================
# NEW - single merged poll endpoint
# ---------------------------------------------------------------------------
# Replaces two separate ESP32 HTTPS calls (device_mode + active_session)
# with one. Each HTTPS call is a full TLS handshake + round trip on the
# ESP32 - merging them removes several seconds of blocking time per poll
# cycle, which was the main cause of the ~6s scan delay.
# ===========================================================================

@api_bp.route("/poll", methods=["GET"])
def poll():
    """
    ESP32 calls this ONCE per poll cycle.

    Query param: ?timetable_id=X (optional - same DEMO_MODE behaviour
    as the old /api/active_session)

    Response (ATTENDANCE):
        { "mode": "ATTENDANCE", "session_id": 7 }   # or null

    Response (ENROLLMENT):
        {
          "mode": "ENROLLMENT",
          "enroll_student_id": 249001,
          "enroll_name": "Kasun Perera",
          "enroll_fingerprint_id": 6
        }

    Response (DELETE):
        {
          "mode": "DELETE",
          "delete_student_id": 249001,
          "delete_fingerprint_id": 6
        }
    """
    state = DeviceState.get_singleton()

    if state.mode == "ENROLLMENT" and state.enroll_student_id is not None:
        student = Student.query.get(state.enroll_student_id)
        return jsonify({
            "mode": "ENROLLMENT",
            "enroll_student_id": state.enroll_student_id,
            "enroll_name": student.name if student else None,
            "enroll_fingerprint_id": _next_free_fingerprint_id(),
        }), 200

    if state.mode == "DELETE" and state.delete_student_id is not None:
        student = Student.query.get(state.delete_student_id)
        if not student or student.fingerprint_id is None:
            # Nothing sensible to delete anymore - bail back to ATTENDANCE
            # instead of leaving the device stuck in DELETE mode.
            state.mode = "ATTENDANCE"
            state.delete_student_id = None
            db.session.commit()
        else:
            return jsonify({
                "mode": "DELETE",
                "delete_student_id": state.delete_student_id,
                "delete_fingerprint_id": student.fingerprint_id,
            }), 200

    timetable_id = request.args.get("timetable_id", type=int)
    query = LectureSession.query.filter_by(status="active")
    if timetable_id is not None:
        query = query.filter_by(timetable_id=timetable_id)
    lecture_session = query.order_by(LectureSession.started_at.desc()).first()

    return jsonify({
        "mode": "ATTENDANCE",
        "session_id": lecture_session.session_id if lecture_session else None,
    }), 200


@api_bp.route("/enroll_result", methods=["POST"])
def enroll_result():
    """
    ESP32 calls this once after attempting a fingerprint enrollment.

    Expected JSON body:
        { "student_id": 249001, "fingerprint_id": 6, "success": true }
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
        return jsonify({"error": "No matching enrollment currently in progress"}), 409

    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    if success and fingerprint_id is not None:
        # Belt-and-braces re-check - the ID was server-assigned this time,
        # so a clash should be very rare, but stay defensive.
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

    state.mode = "ATTENDANCE"
    state.enroll_student_id = None
    state.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "Enrollment result recorded"}), 200


# ===========================================================================
# NEW - delete flow
# ===========================================================================

@api_bp.route("/delete_result", methods=["POST"])
def delete_result():
    """
    ESP32 calls this once after attempting finger.deleteModel(id).

    Expected JSON body:
        { "student_id": 249001, "success": true }
      or:
        { "student_id": 249001, "success": false, "message": "..." }
    """
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    success = bool(data.get("success"))
    message = data.get("message", "")

    state = DeviceState.get_singleton()

    if state.mode != "DELETE" or state.delete_student_id != student_id:
        return jsonify({"error": "No matching delete currently in progress"}), 409

    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    if success:
        student.fingerprint_id = None
        state.delete_status = "success"
        state.delete_message = f"Fingerprint removed for {student.name}"
    else:
        state.delete_status = "failed"
        state.delete_message = message or "Delete failed on device"

    state.mode = "ATTENDANCE"
    state.delete_student_id = None
    state.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "Delete result recorded"}), 200