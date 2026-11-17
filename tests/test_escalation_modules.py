"""
Comprehensive Test Suite for Modules 1-7:
- Voice Emergency detection & deduplication
- Sequential Caretaker Escalation (30s timers, handover)
- Caretaker attendance & emergency resolution
- Admin unacknowledged escalation & override
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException

from backend.database import db_manager
from backend.models import VoiceEmergencyRequest, AcknowledgeAction, ResolveAction
from backend.routers import incidents
from core.incident_state_machine import IncidentStateMachine
from utils.notification_service import CaregiverNotificationService


def test_voice_emergency_endpoint_creation_and_deduplication():
    """Module 1: Voice emergency creates incident assigned to Mohini Ravat, deduplicates duplicates."""
    db_manager.delete_many("incidents", {"camera_id": "MIC-VOICE-01"})

    payload = VoiceEmergencyRequest(
        phrase="Help Me, please",
        resident_id="RES-101",
        resident_name="Elderly Resident / Patient",
        room_id="Resident Bedroom",
    )
    data = incidents.trigger_voice_emergency(payload)
    assert data["emergency_type"] == "VOICE EMERGENCY"
    assert data["status"] in ("PENDING", "ESCALATED_CARETAKER_1")
    assert data["current_assigned_caretaker"] == "Mohini Ravat"

    # Test deduplication cooldown (immediate second call should return existing active)
    repeat_res = incidents.trigger_voice_emergency(payload)
    assert repeat_res["incident_id"] == data["incident_id"]

    # Test non-emergency phrase is rejected
    with pytest.raises(HTTPException) as exc_info:
        incidents.trigger_voice_emergency(VoiceEmergencyRequest(phrase="Good morning assistant"))
    assert exc_info.value.status_code == 400

    # Cleanup test incident
    db_manager.delete_many("incidents", {"incident_id": data["incident_id"]})


def test_sequential_caretaker_escalation_and_cannot_attend():
    """Module 3: Mohini cannot attend -> Radha; Radha cannot attend -> Admin."""
    test_id = f"TEST-SEQ-{datetime.now().strftime('%H%M%S')}"
    inc = IncidentStateMachine.create_incident(
        incident_id=test_id,
        camera_id="CAM-001",
        room_id="Patient Bedroom",
        emergency_type="FALL DETECTION",
        status="PENDING",
        current_assigned_caretaker="Mohini Ravat",
    )
    assert inc["current_assigned_caretaker"] == "Mohini Ravat"

    # Mohini clicks Cannot Attend
    fwd2 = CaregiverNotificationService.forward_alert_to_caretaker2(
        incident_id=test_id,
        room_name="Patient Bedroom",
        reason="Primary caretaker unavailable.",
    )
    assert fwd2["status"] == "ESCALATED_CARETAKER_2"
    doc2 = db_manager.find_one("incidents", {"incident_id": test_id})
    assert doc2["current_assigned_caretaker"] == "Radha Raghav"
    assert doc2["escalation_reason"] == "Primary caretaker unavailable."

    # Radha clicks Cannot Attend -> Escalates to Admin
    fwd_admin = CaregiverNotificationService.forward_alert_to_admin(
        incident_id=test_id,
        room_name="Patient Bedroom",
        reason="Secondary caretaker (Radha Raghav) unavailable. Emergency requires immediate Administrative override.",
    )
    assert fwd_admin["status"] in ("UNACKNOWLEDGED_ADMIN_REQUIRED", "CRITICAL_ADMIN_OVERRIDE")
    doc_admin = db_manager.find_one("incidents", {"incident_id": test_id})
    assert doc_admin["current_assigned_caretaker"] == "System Administrator"
    assert doc_admin["status"] == "UNACKNOWLEDGED_ADMIN_REQUIRED"

    db_manager.delete_many("incidents", {"incident_id": test_id})


def test_caretaker_attending_and_resolving_incident():
    """Module 6: Caretaker attends, acknowledges, and marks resolved with notes."""
    test_id = f"TEST-RES-{datetime.now().strftime('%H%M%S')}"
    IncidentStateMachine.create_incident(
        incident_id=test_id,
        emergency_type="FALL DETECTION",
        status="PENDING",
        current_assigned_caretaker="Mohini Ravat",
    )

    # 1. Caretaker attends
    att_res = incidents.attend_incident(
        incident_id=test_id,
        action=AcknowledgeAction(caretaker_name="Mohini Ravat", notes="Attending patient on-site."),
    )
    doc_att = db_manager.find_one("incidents", {"incident_id": test_id})
    assert doc_att["status"] == "ACKNOWLEDGED"
    assert doc_att["current_assigned_caretaker"] == "Mohini Ravat"
    assert doc_att["acknowledgement_timestamp"] is not None
    assert doc_att["response_deadline_at"] is None  # Countdown stopped

    # 2. Caretaker resolves
    res_res = incidents.resolve_incident(
        incident_id=test_id,
        payload=ResolveAction(resolved_by="Mohini Ravat", notes="Resident assisted and resting comfortably."),
    )
    doc_res = db_manager.find_one("incidents", {"incident_id": test_id})
    assert doc_res["status"] == "RESOLVED"
    assert doc_res["resolved_by"] == "Mohini Ravat"
    assert doc_res["resolution_timestamp"] is not None
    assert "resting comfortably" in doc_res["resolution_notes"]

    db_manager.delete_many("incidents", {"incident_id": test_id})


def test_caretaker1_and_caretaker2_30_second_timeout_auto_forward():
    """Module 3 Steps 4 & 6: 30-second timeout auto-forwards to Caretaker 2, then to Admin."""
    test_id = f"TEST-TIMEOUT-30S-{datetime.now().strftime('%H%M%S')}"
    IncidentStateMachine.create_incident(
        incident_id=test_id,
        emergency_type="FALL DETECTION",
        status="ESCALATED_CARETAKER_1",
        current_assigned_caretaker="Mohini Ravat",
    )
    now = datetime.now(timezone.utc)

    # Simulate Caretaker 1 response window expired (>30s)
    db_manager.update_one(
        "incidents",
        {"incident_id": test_id},
        {"response_deadline_at": (now - timedelta(seconds=1)).isoformat()},
    )
    overdue_c1 = CaregiverNotificationService.process_overdue_escalations(now=now)
    assert test_id in overdue_c1

    doc_after_c1 = db_manager.find_one("incidents", {"incident_id": test_id})
    assert doc_after_c1["status"] == "ESCALATED_CARETAKER_2"
    assert doc_after_c1["current_assigned_caretaker"] == "Radha Raghav"
    assert "Caretaker 1 did not respond within 30 seconds" in doc_after_c1["escalation_reason"]

    # Simulate Caretaker 2 response window expired (>30s)
    db_manager.update_one(
        "incidents",
        {"incident_id": test_id},
        {"response_deadline_at": (now - timedelta(seconds=1)).isoformat()},
    )
    overdue_c2 = CaregiverNotificationService.process_overdue_escalations(now=now)
    assert test_id in overdue_c2

    doc_after_c2 = db_manager.find_one("incidents", {"incident_id": test_id})
    assert doc_after_c2["status"] == "UNACKNOWLEDGED_ADMIN_REQUIRED"
    assert doc_after_c2["current_assigned_caretaker"] == "System Administrator"

    db_manager.delete_many("incidents", {"incident_id": test_id})
