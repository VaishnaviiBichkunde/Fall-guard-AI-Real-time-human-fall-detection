"""
Unit tests for Incident State Machine and Verification Transitions.
"""

from datetime import datetime, timedelta, timezone

import pytest
from core.incident_state_machine import IncidentStateMachine
from backend.database import db_manager


def test_create_incident_lifecycle():
    incident = IncidentStateMachine.create_incident(
        camera_id="cam-test",
        room_id="Bedroom Node #2",
        predicted_activity="Possible Fall",
        body_angle=52.5,
        confidence=0.95,
    )
    assert incident["incident_id"].startswith("INC-")
    assert incident["status"] == "PENDING_VERIFICATION"
    assert len(incident["timeline"]) >= 2

    # Transition to ACKNOWLEDGED_SAFE
    updated = IncidentStateMachine.transition(
        incident_id=incident["incident_id"],
        target_state="ACKNOWLEDGED_SAFE",
        event_note="User confirmed ok via voice command",
    )
    assert updated["status"] == "ACKNOWLEDGED_SAFE"
    assert updated["acknowledged_timestamp"] is not None

    # Transition to CLOSED
    closed = IncidentStateMachine.transition(
        incident_id=incident["incident_id"],
        target_state="CLOSED",
        event_note="Incident verified safe and closed",
        reviewer="Test Nurse",
    )
    assert closed["status"] == "CLOSED"
    assert closed["closed_timestamp"] is not None
    assert closed["reviewer_label"] == "Test Nurse"
    db_manager.delete_many("incidents", {"incident_id": incident["incident_id"]})


def test_disallowed_transition_is_rejected():
    incident = IncidentStateMachine.create_incident(camera_id="cam-test-2")
    # Close it directly
    IncidentStateMachine.transition(incident["incident_id"], "CLOSED")

    # Try to reopen to PENDING_VERIFICATION (not allowed from CLOSED)
    result = IncidentStateMachine.transition(incident["incident_id"], "PENDING_VERIFICATION")
    # Status remains CLOSED
    assert result["status"] == "CLOSED"
    db_manager.delete_many("incidents", {"incident_id": incident["incident_id"]})


def test_tiered_caretaker_handover_and_admin_override():
    from utils.notification_service import CaregiverNotificationService

    # 1. Create incident
    inc = IncidentStateMachine.create_incident(camera_id="cam-handover", room_id="Living Room")
    inc_id = inc["incident_id"]
    assert inc["status"] == "PENDING_VERIFICATION"

    # 2. Caretaker 1 cannot attend -> Forward to Caretaker 2
    fwd2 = CaregiverNotificationService.forward_alert_to_caretaker2(
        incident_id=inc_id,
        room_name="Living Room",
        reason="Mohini Ravat is unavailable to attend"
    )
    assert fwd2["status"] == "ESCALATED_CARETAKER_2"
    assert "Radha" in fwd2["contact"]["name"]
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] == "ESCALATED_CARETAKER_2"

    # 3. Caretaker 2 cannot attend -> Forward to Admin
    fwd_adm = CaregiverNotificationService.forward_alert_to_admin(
        incident_id=inc_id,
        room_name="Living Room",
        reason="Radha Raghav is also unavailable to attend"
    )
    assert fwd_adm["status"] in ("CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED")
    assert "Admin" in fwd_adm["contact"]["name"]
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] in ("CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED")

    # 4. Admin dispatches ambulance
    act_amb = CaregiverNotificationService.admin_take_emergency_action(
        incident_id=inc_id,
        action_type="AMBULANCE",
        details="Admin dispatched ambulance 108"
    )
    assert act_amb["status"] == "AMBULANCE_DISPATCHED"
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] == "ADMIN_ACTION_TAKEN"

    # 5. Admin consults hospital
    act_hosp = CaregiverNotificationService.admin_take_emergency_action(
        incident_id=inc_id,
        action_type="HOSPITAL",
        details="Admin directly consulted Apollo hospital ER"
    )
    assert act_hosp["status"] == "HOSPITAL_CONSULTED"
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] == "ADMIN_ACTION_TAKEN"

    # 6. Admin resolves emergency
    act_res = CaregiverNotificationService.admin_take_emergency_action(
        incident_id=inc_id,
        action_type="RESOLVE",
        details="Patient attended and safe"
    )
    assert act_res["status"] in ("CLOSED", "RESOLVED")
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] in ("CLOSED", "RESOLVED")
    assert doc["closed_by"] == "System Administrator"
    db_manager.delete_many("incidents", {"incident_id": inc_id})


def test_caretaker2_attending_patient_resolves_incident():
    from utils.notification_service import CaregiverNotificationService

    # 1. Create incident
    inc = IncidentStateMachine.create_incident(camera_id="cam-c2", room_id="Patient Room")
    inc_id = inc["incident_id"]

    # 2. Caretaker 1 forwards to Caretaker 2
    CaregiverNotificationService.forward_alert_to_caretaker2(inc_id, "Patient Room")
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] == "ESCALATED_CARETAKER_2"

    # 3. Caretaker 2 responds with patient
    IncidentStateMachine.transition(inc_id, "RESPONDED_CARETAKER_2", "Radha Raghav attended patient")
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] == "RESPONDED_CARETAKER_2"

    # Close incident
    IncidentStateMachine.transition(inc_id, "CLOSED", "Patient verified safe")
    doc = db_manager.find_one("incidents", {"incident_id": inc_id})
    assert doc["status"] == "CLOSED"
    db_manager.delete_many("incidents", {"incident_id": inc_id})


def test_unanswered_alerts_escalate_after_one_minute():
    from utils.notification_service import CaregiverNotificationService

    incident = IncidentStateMachine.create_incident(
        camera_id="cam-timeout",
        room_id="Patient Room",
    )
    incident_id = incident["incident_id"]
    now = datetime.now(timezone.utc)
    db_manager.update_one(
        "incidents",
        {"incident_id": incident_id},
        {
            "status": "ESCALATED_CARETAKER_1",
            "verification_status": "ESCALATED_CARETAKER_1",
            "response_deadline_at": (now + timedelta(seconds=60)).isoformat(),
        },
    )
    assert incident_id not in CaregiverNotificationService.process_overdue_escalations(now=now)

    db_manager.update_one(
        "incidents",
        {"incident_id": incident_id},
        {
            "response_deadline_at": (now - timedelta(seconds=1)).isoformat(),
        },
    )

    escalated = CaregiverNotificationService.process_overdue_escalations(now=now)
    assert incident_id in escalated
    doc = db_manager.find_one("incidents", {"incident_id": incident_id})
    assert doc["status"] == "ESCALATED_CARETAKER_2"
    started_at = datetime.fromisoformat(doc["response_stage_started_at"])
    deadline_at = datetime.fromisoformat(doc["response_deadline_at"])
    assert (deadline_at - started_at).total_seconds() == CaregiverNotificationService.RESPONSE_TIMEOUT_SECONDS

    db_manager.update_one(
        "incidents",
        {"incident_id": incident_id},
        {"response_deadline_at": (now - timedelta(seconds=1)).isoformat()},
    )
    escalated = CaregiverNotificationService.process_overdue_escalations(now=now)
    assert incident_id in escalated
    doc = db_manager.find_one("incidents", {"incident_id": incident_id})
    assert doc["status"] in ("CRITICAL_ADMIN_OVERRIDE", "UNACKNOWLEDGED_ADMIN_REQUIRED")
    db_manager.delete_many("incidents", {"incident_id": incident_id})
