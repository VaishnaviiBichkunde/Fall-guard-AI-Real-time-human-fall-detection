"""Facility-aware emergency assignment and escalation workflow."""

from datetime import datetime, timedelta, timezone
import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException

from backend.database import db_manager

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: Optional[datetime] = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds")


def _response_timeout() -> int:
    raw_value = os.getenv("CARETAKER_RESPONSE_TIMEOUT_SECONDS", "30")
    try:
        timeout = int(raw_value)
    except ValueError:
        logger.error("Invalid CARETAKER_RESPONSE_TIMEOUT_SECONDS %r; using 30 seconds.", raw_value)
        return 30
    if not 5 <= timeout <= 3600:
        logger.error("CARETAKER_RESPONSE_TIMEOUT_SECONDS must be 5..3600; using 30 seconds.")
        return 30
    return timeout


def _timeline_event(
    incident: Dict[str, Any],
    *,
    action: str,
    actor_name: str,
    actor_id: str,
    previous_status: str,
    new_status: str,
    remarks: str = "",
) -> Dict[str, Any]:
    timestamp = _utc_text()
    event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
    event = {
        "event_id": event_id,
        "incident_id": incident["incident_id"],
        "timestamp": timestamp,
        "user_id": actor_id,
        "user_name": actor_name,
        "previous_status": previous_status,
        "new_status": new_status,
        "action": action,
        "remarks": remarks,
    }
    timeline = list(incident.get("timeline", []))
    timeline.append(
        {
            **event,
            "time": datetime.now().astimezone().strftime("%I:%M:%S %p"),
            "utc": timestamp,
            "event": f"{actor_name}: {action}" + (f" — {remarks}" if remarks else ""),
        }
    )
    db_manager.update_one(
        "incidents",
        {"incident_id": incident["incident_id"]},
        {"timeline": timeline},
    )
    db_manager.insert_one("emergency_timeline", event)
    incident["timeline"] = timeline
    return event


def _get_room_for_incident(incident: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    camera_id = incident.get("camera_id")
    room = db_manager.find_one("rooms", {"camera_id": camera_id}) if camera_id else None
    if room:
        return room
    room_value = incident.get("room_id") or incident.get("room_number")
    if not room_value:
        return None
    return (
        db_manager.find_one("rooms", {"room_id": room_value})
        or db_manager.find_one("rooms", {"room_number": room_value})
    )


def _available_caretaker(caretaker_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not caretaker_id:
        return None
    caretaker = db_manager.find_one("local_caretakers", {"caretaker_id": caretaker_id})
    if (
        caretaker
        and caretaker.get("is_active", True)
        and caretaker.get("availability") == "Available"
    ):
        return caretaker
    return None


def get_authorized_incident(incident_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    incident = db_manager.find_one("incidents", {"incident_id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    role = actor.get("role")
    if role == "admin":
        return incident
    if role in {"caretaker_1", "caretaker_2"}:
        expected = "Mohini Ravat" if role == "caretaker_1" else "Radha Raghav"
        assigned_name = (
            (incident.get("active_contact") or {}).get("name")
            or incident.get("current_assigned_caretaker")
        )
        if assigned_name == expected:
            return incident
    elif role == "local_caretaker":
        caretaker_id = actor.get("caretaker_id")
        assignment = db_manager.find_one(
            "caretaker_assignments",
            {"incident_id": incident_id, "caretaker_id": caretaker_id},
        )
        if assignment or incident.get("active_caretaker_id") == caretaker_id:
            return incident
    elif role in {"user", "resident"}:
        resident_id = actor.get("resident_id")
        if not resident_id and actor.get("username") == "user":
            resident_id = "RES-101"
        if resident_id and incident.get("resident_id") == resident_id:
            return incident
    raise HTTPException(status_code=403, detail="You are not assigned to this incident.")


def record_incident_action(
    incident_id: str,
    action: str,
    new_status: str,
    actor: Dict[str, Any],
    remarks: str = "",
) -> Dict[str, Any]:
    if actor.get("role") not in {"admin", "local_caretaker", "caretaker_1", "caretaker_2"}:
        raise HTTPException(status_code=403, detail="Only a responder or administrator can act on an incident.")
    incident = get_authorized_incident(incident_id, actor)
    if actor.get("role") == "local_caretaker" and incident.get("active_caretaker_id") != actor.get("caretaker_id"):
        raise HTTPException(status_code=403, detail="This incident is no longer assigned to you.")
    if incident.get("status") in {"RESOLVED", "CLOSED"}:
        raise HTTPException(status_code=409, detail="Resolved incidents cannot be changed.")

    previous_status = incident.get("status", "UNKNOWN")
    actor_id = actor.get("user_id", actor.get("username", "system"))
    actor_name = actor.get(
        "display_name",
        actor.get("full_name", actor.get("username", "Responder")),
    )
    assignment = None
    if actor.get("caretaker_id"):
        assignment = db_manager.find_one(
            "caretaker_assignments",
            {
                "incident_id": incident_id,
                "caretaker_id": actor["caretaker_id"],
                "is_active": True,
            },
        )

    update: Dict[str, Any] = {}
    if action == "ACCEPTED":
        accepted_at = _utc_text()
        update.update(
            {
                "acknowledged_by": actor_name,
                "acknowledgement_timestamp": accepted_at,
                "response_deadline_at": None,
                "status": "ACKNOWLEDGED",
                "verification_status": "ACKNOWLEDGED",
            }
        )
        new_status = "ACKNOWLEDGED"
        if assignment:
            db_manager.update_one(
                "caretaker_assignments",
                {"assignment_id": assignment["assignment_id"]},
                {"accepted_at": accepted_at},
            )
    elif action == "UNABLE_TO_ATTEND":
        if actor.get("role") not in {"local_caretaker", "caretaker_1", "caretaker_2"}:
            raise HTTPException(status_code=403, detail="This responder cannot forward the incident.")
        if assignment:
            db_manager.update_one(
                "caretaker_assignments",
                {"assignment_id": assignment["assignment_id"]},
                {"is_active": False, "ended_at": _utc_text(), "end_reason": action},
            )
        next_stage = {
            "local_caretaker": "ESCALATED_LOCAL_CARETAKER",
            "caretaker_1": "ESCALATED_CARETAKER_1",
            "caretaker_2": "ESCALATED_CARETAKER_2",
        }[actor["role"]]
        update.update(
            {
                "status": next_stage,
                "verification_status": next_stage,
                "response_deadline_at": _utc_text(),
            }
        )
        if actor.get("role") == "local_caretaker":
            update["active_caretaker_id"] = None
        new_status = next_stage
    elif action in {"ON_THE_WAY", "REACHED_LOCATION", "ASSISTANCE_PROVIDED"}:
        timestamp_field = {
            "ON_THE_WAY": "on_the_way_at",
            "REACHED_LOCATION": "arrival_timestamp",
            "ASSISTANCE_PROVIDED": "assistance_provided_at",
        }[action]
        update.update({timestamp_field: _utc_text(), "response_deadline_at": None})
    elif action == "RESOLVED":
        resolved_at = _utc_text()
        update.update(
            {
                "resolution_timestamp": resolved_at,
                "resolution_notes": remarks or "Assistance provided and resident checked.",
                "resolved_by": actor_name,
                "closed_at": resolved_at,
                "response_deadline_at": None,
                "status": "RESOLVED",
                "verification_status": "RESOLVED",
            }
        )
        if assignment:
            db_manager.update_one(
                "caretaker_assignments",
                {"assignment_id": assignment["assignment_id"]},
                {"is_active": False, "ended_at": resolved_at, "end_reason": "RESOLVED"},
            )
        new_status = "RESOLVED"
    else:
        update.update({"status": new_status, "verification_status": new_status})

    db_manager.update_one("incidents", {"incident_id": incident_id}, update)
    incident.update(update)
    _timeline_event(
        incident,
        action=action,
        actor_name=actor_name,
        actor_id=actor_id,
        previous_status=previous_status,
        new_status=new_status,
        remarks=remarks,
    )
    return db_manager.find_one("incidents", {"incident_id": incident_id}) or incident


def assign_local_caretaker(
    incident: Dict[str, Any],
    caretaker: Dict[str, Any],
    *,
    actor_name: str = "Fall Guard AI",
    actor_id: str = "system",
    remarks: str = "",
) -> Dict[str, Any]:
    incident_id = incident["incident_id"]
    active_assignment = db_manager.find_one(
        "caretaker_assignments",
        {"incident_id": incident_id, "is_active": True},
    )
    if active_assignment:
        if active_assignment.get("caretaker_id") == caretaker["caretaker_id"]:
            return incident
        db_manager.update_one(
            "caretaker_assignments",
            {"assignment_id": active_assignment["assignment_id"]},
            {"is_active": False, "ended_at": _utc_text(), "end_reason": "REASSIGNED"},
        )

    assigned_at = _utc_now()
    assignment_id = f"ASN-{uuid.uuid4().hex[:12].upper()}"
    timeout_at = assigned_at + timedelta(seconds=_response_timeout())
    facility = db_manager.find_one("facilities", {"facility_id": caretaker["facility_id"]})
    room = db_manager.find_one("rooms", {"room_id": caretaker["room_id"]})
    resident_id = (room or {}).get("resident_id") or incident.get("resident_id")
    resident = db_manager.find_one("residents", {"resident_id": resident_id}) if resident_id else None
    previous_status = incident.get("status", "PENDING")
    updated_fields = {
        "facility_id": caretaker["facility_id"],
        "facility_name": (facility or {}).get("name"),
        "room_id": caretaker["room_id"],
        "room_number": (room or {}).get("room_number", incident.get("room_number")),
        "active_caretaker_id": caretaker["caretaker_id"],
        "current_assigned_caretaker": caretaker["full_name"],
        "resident_id": resident_id,
        "resident_name": (resident or {}).get("full_name", incident.get("resident_name")),
        "status": "ESCALATED_LOCAL_CARETAKER",
        "verification_status": "ESCALATED_LOCAL_CARETAKER",
        "response_stage_started_at": _utc_text(assigned_at),
        "response_deadline_at": _utc_text(timeout_at),
        "notification_status": "IN_APP_SENT",
        "alert_routed_at": _utc_text(assigned_at),
    }
    db_manager.update_one("incidents", {"incident_id": incident_id}, updated_fields)
    incident.update(updated_fields)
    db_manager.insert_one(
        "caretaker_assignments",
        {
            "assignment_id": assignment_id,
            "incident_id": incident_id,
            "caretaker_id": caretaker["caretaker_id"],
            "facility_id": caretaker["facility_id"],
            "room_id": caretaker["room_id"],
            "assigned_at": _utc_text(assigned_at),
            "is_active": True,
            "response_deadline_at": _utc_text(timeout_at),
        },
    )
    _timeline_event(
        incident,
        action="LOCAL_CARETAKER_ASSIGNED",
        actor_name=actor_name,
        actor_id=actor_id,
        previous_status=previous_status,
        new_status="ESCALATED_LOCAL_CARETAKER",
        remarks=remarks or f"Assigned to {caretaker['full_name']}.",
    )

    from utils.notification_service import CaregiverNotificationService

    CaregiverNotificationService.notify_recipient(
        incident=incident,
        recipient_id=caretaker["caretaker_id"],
        recipient_name=caretaker["full_name"],
        recipient_email=caretaker.get("email", ""),
        stage="local_caretaker",
    )
    return incident


class EmergencyRoutingService:
    """Assigns facilities emergencies locally before using the remote escalation chain."""

    @classmethod
    def route_incident(cls, incident_id: str) -> Dict[str, Any]:
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")
        if incident.get("status") in {"RESOLVED", "CLOSED", "ACKNOWLEDGED_SAFE"}:
            return incident
        if incident.get("alert_routed_at"):
            return incident

        existing_assignment = db_manager.find_one(
            "caretaker_assignments",
            {"incident_id": incident_id, "is_active": True},
        )
        if existing_assignment:
            return incident

        room = _get_room_for_incident(incident)
        if room:
            resident = db_manager.find_one("residents", {"resident_id": room.get("resident_id")}) if room.get("resident_id") else None
            db_manager.update_one(
                "incidents",
                {"incident_id": incident_id},
                {
                    "facility_id": room.get("facility_id"),
                    "room_id": room.get("room_id", incident.get("room_id")),
                    "room_number": room.get("room_number", incident.get("room_number")),
                    "resident_id": (resident or {}).get("resident_id", incident.get("resident_id")),
                    "resident_name": (resident or {}).get("full_name", incident.get("resident_name")),
                },
            )
            incident.update(db_manager.find_one("incidents", {"incident_id": incident_id}) or {})
            assigned = _available_caretaker(room.get("assigned_caretaker_id"))
            if not assigned:
                primary = db_manager.find_one(
                    "local_caretakers",
                    {"caretaker_id": room.get("assigned_caretaker_id")},
                ) if room.get("assigned_caretaker_id") else None
                backup_id = room.get("backup_caretaker_id") or (primary or {}).get("backup_caretaker_id")
                assigned = _available_caretaker(backup_id)
            if assigned:
                return assign_local_caretaker(incident, assigned)

        from utils.notification_service import CaregiverNotificationService

        result = CaregiverNotificationService.dispatch_tiered_escalation(
            incident_id=incident_id,
            room_name=incident.get("room_id", "Resident Room"),
            timestamp=incident.get("detected_at", ""),
            body_angle=incident.get("body_angle_degrees", 0.0),
        )
        db_manager.update_one(
            "incidents",
            {"incident_id": incident_id},
            {"alert_routed_at": _utc_text()},
        )
        result["alert_routed_at"] = _utc_text()
        return result

    @classmethod
    def escalate_local_caretaker(cls, incident: Dict[str, Any]) -> Dict[str, Any]:
        incident_id = incident["incident_id"]
        current_id = incident.get("active_caretaker_id")
        current = db_manager.find_one("local_caretakers", {"caretaker_id": current_id}) if current_id else None
        room = _get_room_for_incident(incident)
        backup_id = (room or {}).get("backup_caretaker_id") or (current or {}).get("backup_caretaker_id")
        backup = _available_caretaker(backup_id)
        if backup and backup_id != current_id:
            return assign_local_caretaker(
                incident,
                backup,
                remarks="Primary local caretaker did not respond within the configured response period.",
            )

        if current_id:
            active_assignment = db_manager.find_one(
                "caretaker_assignments",
                {"incident_id": incident_id, "caretaker_id": current_id, "is_active": True},
            )
            if active_assignment:
                db_manager.update_one(
                    "caretaker_assignments",
                    {"assignment_id": active_assignment["assignment_id"]},
                    {
                        "is_active": False,
                        "ended_at": _utc_text(),
                        "end_reason": "NO_RESPONSE",
                    },
                )
        from utils.notification_service import CaregiverNotificationService

        return CaregiverNotificationService.dispatch_tiered_escalation(
            incident_id=incident_id,
            room_name=incident.get("room_id", "Resident Room"),
            timestamp=incident.get("detected_at", ""),
            body_angle=incident.get("body_angle_degrees", 0.0),
        )
