"""
Incident State Machine and Emergency Verification Workflow Manager.
Enforces valid state transitions, timestamps in UTC, and prevents duplicate alerts.
States: DETECTED -> PENDING_VERIFICATION -> ACKNOWLEDGED_SAFE / HELP_REQUESTED / ESCALATED -> CLOSED
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid

from backend.database import db_manager


VALID_TRANSITIONS = {
    "DETECTED": ["PENDING_VERIFICATION", "PENDING", "CLOSED", "RESOLVED"],
    "PENDING_VERIFICATION": [
        "ACKNOWLEDGED_SAFE", "HELP_REQUESTED", "ESCALATED", "PENDING",
        "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED",
        "ACKNOWLEDGED", "CLOSED", "RESOLVED"
    ],
    "PENDING": [
        "ACKNOWLEDGED", "ACKNOWLEDGED_SAFE", "HELP_REQUESTED", "ESCALATED",
        "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED",
        "CLOSED", "RESOLVED"
    ],
    "ACKNOWLEDGED_SAFE": ["CLOSED", "RESOLVED"],
    "HELP_REQUESTED": [
        "ESCALATED", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED",
        "RESPONDED_CARETAKER_1", "RESPONDED_CARETAKER_2", "ACKNOWLEDGED", "CLOSED", "RESOLVED"
    ],
    "ESCALATED": [
        "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED",
        "RESPONDED_CARETAKER_1", "RESPONDED_CARETAKER_2", "ACKNOWLEDGED", "ADMIN_ACTION_TAKEN", "CLOSED", "RESOLVED"
    ],
    "ESCALATED_CARETAKER_1": [
        "ESCALATED_CARETAKER_2", "CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED",
        "RESPONDED_CARETAKER_1", "ACKNOWLEDGED", "CLOSED", "RESOLVED"
    ],
    "ESCALATED_CARETAKER_2": [
        "CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED",
        "RESPONDED_CARETAKER_2", "ACKNOWLEDGED", "CLOSED", "RESOLVED"
    ],
    "UNACKNOWLEDGED_ADMIN_REQUIRED": [
        "ADMIN_ACTION_TAKEN", "ACKNOWLEDGED", "CLOSED", "RESOLVED"
    ],
    "CRITICAL_ADMIN_OVERRIDE": [
        "ADMIN_ACTION_TAKEN", "UNACKNOWLEDGED_ADMIN_REQUIRED", "ACKNOWLEDGED", "CLOSED", "RESOLVED"
    ],
    "RESPONDED_CARETAKER_1": ["ACKNOWLEDGED", "CLOSED", "RESOLVED"],
    "RESPONDED_CARETAKER_2": ["ACKNOWLEDGED", "CLOSED", "RESOLVED"],
    "ACKNOWLEDGED": ["CLOSED", "RESOLVED", "ADMIN_ACTION_TAKEN"],
    "ADMIN_ACTION_TAKEN": ["ADMIN_ACTION_TAKEN", "CLOSED", "RESOLVED"],
    "RESOLVED": [],
    "CLOSED": [],
}


class IncidentStateMachine:
    """Manages the full lifecycle of suspected fall incidents."""

    @staticmethod
    def get_utc_now() -> str:
        """Returns current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def get_local_now() -> str:
        """Returns current local time formatted for human display."""
        return datetime.now().strftime("%I:%M:%S %p")

    @staticmethod
    def create_incident(
        camera_id: str = "CAM-001",
        room_id: str = "Living Room",
        event_type: str = "Possible Fall",
        detection_evidence: Optional[List[str]] = None,
        body_angle: float = 0.0,
        incident_id: Optional[str] = None,
        predicted_activity: Optional[str] = None,
        confidence: float = 0.9,
        resident_id: str = "RES-101",
        resident_name: str = "Elderly Resident / Patient",
        emergency_type: Optional[str] = None,
        emergency_description: Optional[str] = None,
        status: Optional[str] = None,
        current_assigned_caretaker: str = "Mohini Ravat",
    ) -> Dict[str, Any]:
        """Creates a new incident record in PENDING / PENDING_VERIFICATION state."""
        now_utc = IncidentStateMachine.get_utc_now()
        local_time = IncidentStateMachine.get_local_now()

        if not incident_id:
            incident_id = f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        actual_event_type = emergency_type or predicted_activity or event_type
        init_status = status or "PENDING_VERIFICATION"
        desc = emergency_description or f"Emergency event ({actual_event_type}) recorded at {room_id}."

        evidence_list = detection_evidence or [
            f"Movement event observed: {desc} (Torso angle {body_angle:.1f}°).",
            "Emergency workflow initiated — Primary Caretaker (Mohini Ravat) notified.",
        ]

        timeline = [
            {
                "time": local_time,
                "utc": now_utc,
                "event": f"Emergency [{actual_event_type}] registered at {room_id}. Assigned to {current_assigned_caretaker}.",
            },
            {
                "time": local_time,
                "utc": now_utc,
                "event": f"Dispatched immediate alert to {current_assigned_caretaker}.",
            },
        ]

        # 30-second response window for Caretaker 1
        from datetime import timedelta
        stage_start = datetime.now(timezone.utc)
        stage_deadline = stage_start + timedelta(seconds=30)

        doc = {
            "incident_id": incident_id,
            "resident_id": resident_id,
            "resident_name": resident_name,
            "camera_id": camera_id,
            "room_id": room_id,
            "room_number": room_id,
            "detected_at": now_utc,
            "original_emergency_timestamp": now_utc,
            "event_type": actual_event_type,
            "emergency_type": actual_event_type,
            "emergency_description": desc,
            "body_angle_degrees": round(body_angle, 1),
            "detection_evidence": evidence_list,
            "verification_status": init_status,
            "status": init_status,
            "incident_status": init_status,
            "current_assigned_caretaker": current_assigned_caretaker,
            "user_response": "NONE",
            "response_timestamp": None,
            "acknowledgement_timestamp": None,
            "escalation_timestamp": None,
            "escalation_reason": None,
            "resolution_timestamp": None,
            "resolution_notes": None,
            "notification_status": "PENDING",
            "caregiver_notification_status": "PENDING",
            "response_stage_started_at": stage_start.isoformat(timespec="seconds"),
            "response_deadline_at": stage_deadline.isoformat(timespec="seconds"),
            "closed_at": None,
            "timeline": timeline,
            "escalation_history": timeline,
        }

        db_manager.insert_one("incidents", doc)
        return doc

    @staticmethod
    def acknowledge_incident(incident_id: str, caretaker_name: str = "Mohini Ravat", notes: str = "") -> Optional[Dict[str, Any]]:
        """Caretaker acknowledges emergency ('I AM ATTENDING / RESPONDING TO PATIENT')."""
        now_utc = IncidentStateMachine.get_utc_now()
        local_time = IncidentStateMachine.get_local_now()
        note = f"{caretaker_name} acknowledged emergency and is on-site with patient. {notes}".strip()
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        if not incident:
            return None
        timeline = incident.get("timeline", [])
        timeline.append({"time": local_time, "utc": now_utc, "event": note})
        update_fields = {
            "status": "ACKNOWLEDGED",
            "verification_status": "ACKNOWLEDGED",
            "incident_status": "ACKNOWLEDGED",
            "current_assigned_caretaker": caretaker_name,
            "acknowledgement_timestamp": now_utc,
            "acknowledged_by": caretaker_name,
            "timeline": timeline,
            "escalation_history": timeline,
            "response_deadline_at": None,  # Stop countdown & stop further escalation
        }
        db_manager.update_one("incidents", {"incident_id": incident_id}, update_fields)
        incident.update(update_fields)
        return incident

    @staticmethod
    def resolve_incident(incident_id: str, resolved_by: str = "Caretaker", notes: str = "") -> Optional[Dict[str, Any]]:
        """Caretaker or Admin marks the emergency as RESOLVED."""
        now_utc = IncidentStateMachine.get_utc_now()
        local_time = IncidentStateMachine.get_local_now()
        note = f"Emergency marked RESOLVED by {resolved_by}. Resolution Notes: {notes or 'Patient safe and stabilized.'}".strip()
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        if not incident:
            return None
        timeline = incident.get("timeline", [])
        timeline.append({"time": local_time, "utc": now_utc, "event": note})
        update_fields = {
            "status": "RESOLVED",
            "verification_status": "RESOLVED",
            "incident_status": "RESOLVED",
            "resolution_timestamp": now_utc,
            "resolution_notes": notes or "Patient confirmed safe and attended.",
            "resolved_by": resolved_by,
            "closed_at": now_utc,
            "timeline": timeline,
            "escalation_history": timeline,
            "response_deadline_at": None,  # Stop all timers and escalation
        }
        db_manager.update_one("incidents", {"incident_id": incident_id}, update_fields)
        incident.update(update_fields)
        return incident

    @staticmethod
    def transition(
        incident_id: str,
        target_state: str,
        event_note: str = "",
        reviewer: Optional[str] = None,
        user_response: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Safely transitions an incident to target_state if permitted by the state machine."""
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        if not incident:
            return None

        current_state = incident.get("verification_status") or incident.get("status", "DETECTED")
        allowed = VALID_TRANSITIONS.get(current_state, [])

        if target_state not in allowed:
            # Transition disallowed by state machine
            return incident

        now_utc = IncidentStateMachine.get_utc_now()
        local_time = IncidentStateMachine.get_local_now()

        timeline = incident.get("timeline", [])
        timeline.append({
            "time": local_time,
            "utc": now_utc,
            "event": f"State updated to {target_state}. {event_note}".strip(),
        })

        update_fields: Dict[str, Any] = {
            "verification_status": target_state,
            "status": target_state,
            "timeline": timeline,
        }

        if user_response:
            update_fields["user_response"] = user_response

        if target_state == "ACKNOWLEDGED_SAFE":
            update_fields["response_timestamp"] = now_utc
            update_fields["acknowledged_timestamp"] = now_utc
            if not user_response:
                update_fields["user_response"] = "I_AM_OK"

        elif target_state == "HELP_REQUESTED":
            update_fields["response_timestamp"] = now_utc
            if not user_response:
                update_fields["user_response"] = "I_NEED_HELP"

        elif target_state == "ESCALATED":
            update_fields["escalation_timestamp"] = now_utc
            if not user_response:
                update_fields["user_response"] = "TIMEOUT"

        elif target_state == "ACKNOWLEDGED":
            update_fields["acknowledgement_timestamp"] = now_utc
            update_fields["response_deadline_at"] = None
            if reviewer:
                update_fields["acknowledged_by"] = reviewer
                update_fields["current_assigned_caretaker"] = reviewer

        elif target_state in ("CLOSED", "RESOLVED"):
            update_fields["closed_at"] = now_utc
            update_fields["closed_timestamp"] = now_utc
            update_fields["resolution_timestamp"] = now_utc
            update_fields["response_deadline_at"] = None
            if reviewer:
                update_fields["closed_by"] = reviewer
                update_fields["resolved_by"] = reviewer
                update_fields["reviewer_label"] = reviewer

        db_manager.update_one("incidents", {"incident_id": incident_id}, update_fields)
        incident.update(update_fields)
        return incident

    @staticmethod
    def respond_i_am_ok(incident_id: str, source: str = "BUTTON", notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """User confirms safety ('I'M OK')."""
        suffix = f" Note: {notes}" if notes else ""
        note = f"User confirmed safety ('I'M OK') via {source}. Escalation canceled.{suffix}"
        return IncidentStateMachine.transition(
            incident_id=incident_id,
            target_state="ACKNOWLEDGED_SAFE",
            event_note=note,
            user_response="I_AM_OK",
        )

    @staticmethod
    def respond_need_help(incident_id: str, source: str = "BUTTON") -> Optional[Dict[str, Any]]:
        """User requests urgent help ('I NEED HELP')."""
        note = f"User requested emergency assistance ('I NEED HELP') via {source}."
        return IncidentStateMachine.transition(
            incident_id=incident_id,
            target_state="HELP_REQUESTED",
            event_note=note,
            user_response="I_NEED_HELP",
        )

    @staticmethod
    def handle_countdown_timeout(incident_id: str) -> Optional[Dict[str, Any]]:
        """Verification countdown expired without response -> Auto-escalate."""
        note = "Verification countdown expired without user confirmation. Auto-escalating incident to caregivers."
        return IncidentStateMachine.transition(
            incident_id=incident_id,
            target_state="ESCALATED",
            event_note=note,
            user_response="TIMEOUT",
        )

    @staticmethod
    def record_resident_verification(
        incident_id: str,
        response: str,
        source: str = "BUTTON",
    ) -> Optional[Dict[str, Any]]:
        """Record resident verification without changing the responder escalation state."""
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        if not incident:
            return None
        now_utc = IncidentStateMachine.get_utc_now()
        local_time = IncidentStateMachine.get_local_now()
        response_value = response.upper()
        event = {
            "time": local_time,
            "utc": now_utc,
            "event": f"Resident verification response: {response_value} via {source}.",
        }
        timeline = list(incident.get("timeline", []))
        timeline.append(event)
        update_fields = {
            "resident_verification_status": response_value,
            "resident_verification_timestamp": now_utc,
            "resident_verification_source": source,
            "user_response": response_value,
            "response_timestamp": now_utc,
            "timeline": timeline,
        }
        if response_value == "I_AM_OK":
            update_fields["response_deadline_at"] = None
        db_manager.update_one("incidents", {"incident_id": incident_id}, update_fields)
        incident.update(update_fields)
        return incident
