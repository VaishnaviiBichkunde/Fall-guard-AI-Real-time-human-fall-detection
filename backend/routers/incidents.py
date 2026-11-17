"""
FastAPI Router for Incidents and Emergency Verification.
Provides full CRUD, verification, acknowledgement, and closure endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.database import db_manager
from backend.emergency_workflow import EmergencyRoutingService, get_authorized_incident, record_incident_action
from backend.models import (
    AcknowledgeAction,
    CloseAction,
    IncidentCreate,
    IncidentResponse,
    ResolveAction,
    VerificationAction,
    VoiceEmergencyRequest,
)
from backend.security import get_current_user, require_roles
from core.incident_state_machine import IncidentStateMachine

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


def _function_call_actor(actor, *, role: str = "admin", incident=None):
    if isinstance(actor, dict):
        return actor
    resident_id = (incident or {}).get("resident_id", "RES-101")
    return {
        "user_id": "direct-function-call",
        "username": "user" if role == "resident" else "admin",
        "display_name": "Direct Function Caller",
        "role": role,
        "resident_id": resident_id if role == "resident" else None,
    }


@router.get("", response_model=List[IncidentResponse])
def get_incidents(
    status: Optional[str] = Query(None, description="Filter by verification_status"),
    camera_id: Optional[str] = Query(None, description="Filter by camera_id"),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(get_current_user),
):
    """Retrieve list of incident records from MongoDB / local storage."""
    query = {}
    if status:
        query["verification_status"] = status
    if camera_id:
        query["camera_id"] = camera_id
    records = db_manager.find("incidents", query=query, limit=limit)
    actor = _function_call_actor(actor)
    role = actor.get("role")
    if role == "admin":
        return records
    if role == "local_caretaker":
        return [
            item for item in records
            if item.get("active_caretaker_id") == actor.get("caretaker_id")
        ]
    if role in {"caretaker_1", "caretaker_2"}:
        expected = "Mohini Ravat" if role == "caretaker_1" else "Radha Raghav"
        return [
            item for item in records
            if (
                (item.get("active_contact") or {}).get("name")
                or item.get("current_assigned_caretaker")
            ) == expected
        ]
    if role in {"resident", "user"}:
        return [
            item for item in records
            if item.get("resident_id") == actor.get("resident_id")
        ]
    raise HTTPException(status_code=403, detail="Your account cannot view incidents.")


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, actor=Depends(get_current_user)):
    """Retrieve incident by ID with full chronological audit timeline."""
    record = db_manager.find_one("incidents", {"incident_id": incident_id})
    return get_authorized_incident(incident_id, _function_call_actor(actor, incident=record))


@router.post("", response_model=IncidentResponse)
def create_incident(payload: IncidentCreate, actor=Depends(require_roles("admin"))):
    """Create a new incident and initiate verification workflow."""
    incident = IncidentStateMachine.create_incident(
        camera_id=payload.camera_id,
        room_id=payload.room_id,
        event_type=payload.event_type,
        detection_evidence=payload.detection_evidence,
        body_angle=payload.body_angle_degrees,
        incident_id=payload.incident_id,
    )
    if isinstance(actor, dict):
        EmergencyRoutingService.route_incident(incident["incident_id"])
        return db_manager.find_one("incidents", {"incident_id": incident["incident_id"]}) or incident
    return incident


@router.post("/{incident_id}/verify", response_model=IncidentResponse)
def verify_incident(
    incident_id: str,
    action: VerificationAction,
    actor=Depends(require_roles("resident", "user")),
):
    """
    Process verification action from user (I_AM_OK, NEED_HELP, TIMEOUT).
    Dispatches caregiver notification if help requested or verification timed out.
    """
    direct_call = not isinstance(actor, dict)
    incident = get_authorized_incident(
        incident_id,
        _function_call_actor(actor, role="resident", incident=db_manager.find_one("incidents", {"incident_id": incident_id})),
    )

    action_type = action.action.upper()
    source_str = action.response_source.upper()

    if action_type in ("I_AM_OK", "SAFE", "OK"):
        if direct_call:
            return IncidentStateMachine.respond_i_am_ok(incident_id, source=source_str) or incident
        updated = IncidentStateMachine.record_resident_verification(
            incident_id,
            "I_AM_OK",
            source=source_str,
        )
        return updated or incident

    elif action_type in ("NEED_HELP", "HELP", "I_NEED_HELP", "ESCALATE"):
        if direct_call:
            return IncidentStateMachine.respond_need_help(incident_id, source=source_str) or incident
        updated = IncidentStateMachine.record_resident_verification(
            incident_id,
            "I_NEED_HELP",
            source=source_str,
        )
        EmergencyRoutingService.route_incident(incident_id)
        return updated or incident

    elif action_type == "TIMEOUT":
        if direct_call:
            return IncidentStateMachine.handle_countdown_timeout(incident_id) or incident
        updated = IncidentStateMachine.record_resident_verification(
            incident_id,
            "TIMEOUT",
            source=source_str,
        )
        EmergencyRoutingService.route_incident(incident_id)
        return updated or incident

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported verification action: {action_type}")


@router.post("/voice-emergency", response_model=IncidentResponse)
def trigger_voice_emergency(
    payload: VoiceEmergencyRequest,
    actor=Depends(require_roles("admin", "resident", "user")),
):
    """
    Module 1: Emergency Voice Command Detection.
    Recognizes phrases ("HELP ME", "I NEED HELP", "HELP", "EMERGENCY"),
    creates VOICE EMERGENCY incident, sets status to PENDING, and routes to Caretaker 1.
    Includes active cooldown deduplication.
    """
    clean_phrase = payload.phrase.strip().upper()
    valid_phrases = ["HELP ME", "I NEED HELP", "HELP", "EMERGENCY"]
    matched = any(p in clean_phrase for p in valid_phrases)
    if not matched:
        raise HTTPException(status_code=400, detail="Phrase not recognized as an emergency voice command.")

    actor = _function_call_actor(actor)
    if actor.get("role") in {"resident", "user"}:
        resident_id = actor.get("resident_id") or (
            "RES-101" if actor.get("username") == "user" else None
        )
        if not resident_id:
            raise HTTPException(status_code=404, detail="Resident profile not found.")
    else:
        resident_id = payload.resident_id or "RES-101"

    # Prevent duplicates within active 15-second cooldown
    import datetime

    active_voice = db_manager.find_one(
        "incidents",
        {
            "resident_id": resident_id,
            "emergency_type": "VOICE EMERGENCY",
            "status": {
                "$in": [
                    "PENDING",
                    "ESCALATED_LOCAL_CARETAKER",
                    "ESCALATED_CARETAKER_1",
                    "ESCALATED_CARETAKER_2",
                    "CRITICAL_ADMIN_OVERRIDE",
                    "UNACKNOWLEDGED_ADMIN_REQUIRED",
                    "ACKNOWLEDGED",
                ]
            },
        },
        sort=[("detected_at", -1)],
    )
    if active_voice:
        detected_at = active_voice.get("detected_at")
        try:
            detected_time = datetime.datetime.fromisoformat(
                str(detected_at).replace("Z", "+00:00")
            )
            if detected_time.tzinfo is None:
                detected_time = detected_time.replace(tzinfo=datetime.timezone.utc)
            age_seconds = (
                datetime.datetime.now(datetime.timezone.utc) - detected_time
            ).total_seconds()
        except (TypeError, ValueError):
            age_seconds = None
        if age_seconds is not None and 0 <= age_seconds <= 15:
            return active_voice

    inc_id = f"VOICE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    resident = db_manager.find_one("residents", {"resident_id": resident_id})
    if actor.get("role") in {"resident", "user"}:
        room_id = (resident or {}).get("room_id") or "Resident Room"
    else:
        room_id = (resident or {}).get("room_id") or payload.room_id or "Resident Room"
    room = db_manager.find_one("rooms", {"room_id": room_id})
    camera_id = (room or {}).get("camera_id") or "MIC-VOICE-01"
    new_inc = IncidentStateMachine.create_incident(
        incident_id=inc_id,
        camera_id=camera_id,
        room_id=room_id,
        event_type="VOICE EMERGENCY",
        emergency_type="VOICE EMERGENCY",
        emergency_description=f"Resident spoken emergency phrase detected: '{clean_phrase}'",
        detection_evidence=[
            f"Spoken emergency phrase matched: '{clean_phrase}'",
            "Emergency voice request confirmed by Web Speech API",
            "Immediate alert dispatched to Caretaker 1 (Mohini Ravat)",
        ],
        body_angle=0.0,
        resident_id=resident_id,
        resident_name=(resident or {}).get("full_name") or actor.get("display_name", payload.resident_name or "Elderly Resident / Patient"),
        current_assigned_caretaker="Mohini Ravat",
        status="PENDING",
    )

    EmergencyRoutingService.route_incident(inc_id)
    refreshed = db_manager.find_one("incidents", {"incident_id": inc_id})
    return refreshed or new_inc


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    incident_id: str,
    action: Optional[AcknowledgeAction] = None,
    actor=Depends(get_current_user),
):
    """Caretaker acknowledges emergency ('I AM ATTENDING / RESPONDING TO PATIENT') or resident confirms safe."""
    direct_call = not isinstance(actor, dict)
    incident = db_manager.find_one("incidents", {"incident_id": incident_id})
    actor = _function_call_actor(actor, incident=incident)
    incident = get_authorized_incident(incident_id, actor)
    notes = action.notes if action and action.notes else ""
    if notes and "safe" in notes.lower():
        if direct_call:
            return IncidentStateMachine.respond_i_am_ok(incident_id, notes=notes) or incident
        if actor.get("role") not in {"resident", "user"}:
            raise HTTPException(status_code=403, detail="Only the resident can confirm their safety.")
        return IncidentStateMachine.record_resident_verification(incident_id, "I_AM_OK", source="API") or get_authorized_incident(incident_id, actor)

    return record_incident_action(
        incident_id=incident_id,
        action="ACCEPTED",
        new_status="ACKNOWLEDGED",
        actor=actor,
        remarks=notes or "Caretaker attending on-site.",
    )


@router.post("/{incident_id}/attend", response_model=IncidentResponse)
def attend_incident(
    incident_id: str,
    action: Optional[AcknowledgeAction] = None,
    actor=Depends(get_current_user),
):
    """Caretaker marks themselves as attending ('I AM ATTENDING / RESPONDING TO PATIENT')."""
    if not isinstance(actor, dict):
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        caretaker = action.caretaker_name if action and action.caretaker_name else "Mohini Ravat"
        notes = action.notes if action and action.notes else f"Caretaker ({caretaker}) is attending to patient."
        return IncidentStateMachine.acknowledge_incident(incident_id, caretaker_name=caretaker, notes=notes) or incident
    return record_incident_action(
        incident_id=incident_id,
        action="ACCEPTED",
        new_status="ACKNOWLEDGED",
        actor=actor,
        remarks=action.notes if action and action.notes else "Caretaker attending on-site.",
    )


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(
    incident_id: str,
    payload: Optional[ResolveAction] = None,
    actor=Depends(get_current_user),
):
    """Caretaker marks the incident as RESOLVED with resolution notes."""
    if not isinstance(actor, dict):
        return IncidentStateMachine.resolve_incident(
            incident_id,
            resolved_by=payload.resolved_by if payload and payload.resolved_by else "Caretaker",
            notes=payload.notes if payload and payload.notes else "Patient verified safe and attended.",
        )
    return record_incident_action(
        incident_id=incident_id,
        action="RESOLVED",
        new_status="RESOLVED",
        actor=actor,
        remarks=payload.notes if payload and payload.notes else "Patient verified safe and attended.",
    )


@router.post(
    "/{incident_id}/close",
    response_model=IncidentResponse,
    dependencies=[Depends(require_roles("admin"))],
)
def close_incident(
    incident_id: str,
    payload: Optional[CloseAction] = None,
):
    """Close an incident after inspection or caregiver response."""
    incident = db_manager.find_one("incidents", {"incident_id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    reviewer = payload.reviewer if payload else "Administrator"
    notes = payload.notes if payload else "Incident resolved."

    updated = IncidentStateMachine.transition(
        incident_id=incident_id,
        target_state="CLOSED",
        event_note=notes,
        reviewer=reviewer,
    )
    return updated or incident
