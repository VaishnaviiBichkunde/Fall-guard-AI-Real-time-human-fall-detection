"""
Direct unit and integration tests for FastAPI REST Router Functions.
"""

import pytest
from backend.database import db_manager
from backend.models import AcknowledgeAction, CloseAction, IncidentCreate, VerificationAction
from backend.routers import incidents, caregivers
from backend.main import root, api_health, api_status


def test_root_endpoint():
    data = root()
    assert data["system"] == "Fall Guard AI Backend"
    assert data["version"] == "2.0.0"
    assert data["status"] == "ONLINE"


def test_health_endpoint():
    data = api_health()
    assert data["status"] == "healthy"
    assert "mongodb_connected" in data


def test_status_endpoint():
    data = api_status()
    assert data["status"] == "MONITORING_ACTIVE"
    assert "pending_verifications" in data


def test_incidents_router_workflow():
    import uuid
    test_id = f"INC-TEST-{uuid.uuid4().hex[:6]}"
    # 1. Create Incident via Router
    payload = IncidentCreate(
        incident_id=test_id,
        camera_id="CAM-001",
        room_id="Living Room",
        event_type="Possible Fall",
        body_angle_degrees=65.5,
        detection_evidence=["Rapid drop observed", "Low posture maintained"],
    )
    inc = incidents.create_incident(payload)
    assert inc["incident_id"] == test_id
    assert inc["verification_status"] == "PENDING_VERIFICATION"

    # 2. Get Incident by ID
    fetched = incidents.get_incident(inc["incident_id"])
    assert fetched["incident_id"] == inc["incident_id"]
    assert len(fetched["detection_evidence"]) >= 1

    # 3. Verify Incident Safe via verify endpoint
    v_action = VerificationAction(
        incident_id=inc["incident_id"],
        action="I_AM_OK",
        response_source="VOICE",
    )
    verified = incidents.verify_incident(inc["incident_id"], v_action)
    assert verified["verification_status"] == "ACKNOWLEDGED_SAFE"
    assert verified["user_response"] == "I_AM_OK"

    # 4. Close Incident
    close_action = CloseAction(reviewer="Administrator", notes="Verified safe and resolved.")
    closed = incidents.close_incident(inc["incident_id"], close_action)
    assert closed["verification_status"] == "CLOSED"
    assert closed["closed_at"] is not None
    db_manager.delete_many("incidents", {"incident_id": inc["incident_id"]})


def test_acknowledge_endpoint():
    import uuid
    ack_id = f"INC-TEST-ACK-{uuid.uuid4().hex[:6]}"
    payload = IncidentCreate(
        incident_id=ack_id,
        camera_id="CAM-002",
        room_id="Bedroom",
        event_type="Possible Fall",
        body_angle_degrees=58.0,
    )
    inc = incidents.create_incident(payload)
    ack_res = incidents.acknowledge_incident(inc["incident_id"], AcknowledgeAction(notes="Confirmed safe by resident"))
    assert ack_res["verification_status"] == "ACKNOWLEDGED_SAFE"
    db_manager.delete_many("incidents", {"incident_id": inc["incident_id"]})


def test_caregivers_router():
    contacts = caregivers.get_caregivers()
    assert isinstance(contacts, list)
    assert len(contacts) >= 1

    test_notif = caregivers.send_test_notification()
    assert "status" in test_notif
    assert test_notif["status"] in ("SENT", "NOT_CONFIGURED", "FAILED")
