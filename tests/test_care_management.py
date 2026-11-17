from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import backend.database as database
from backend.care_models import (
    CareAvailability,
    FacilityCreate,
    FacilityType,
    LocalCaretakerCreate,
    ResidentCreate,
    RoomCreate,
)
from backend.database import db_manager
from backend.emergency_workflow import (
    EmergencyRoutingService,
    get_authorized_incident,
    record_incident_action,
)
from backend.routers.care_management import (
    register_facility,
    register_local_caretaker,
    register_resident,
    register_room,
)
from core.incident_state_machine import IncidentStateMachine
from utils.notification_service import CaregiverNotificationService


@pytest.fixture
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db_manager, "_local_cache", {})
    monkeypatch.setattr(db_manager, "is_connected", False)
    monkeypatch.setattr(
        CaregiverNotificationService,
        "is_configured",
        staticmethod(lambda: False),
    )
    return db_manager


def _seed_room_team(db):
    db.insert_one(
        "facilities",
        {
            "facility_id": "FAC-1",
            "name": "North Care",
            "facility_type": "Old Age Home",
            "is_active": True,
        },
    )
    db.insert_one(
        "rooms",
        {
            "room_id": "ROOM-1",
            "facility_id": "FAC-1",
            "room_number": "101",
            "camera_id": "CAM-1",
            "resident_id": "RES-1",
            "assigned_caretaker_id": "CARE-1",
            "backup_caretaker_id": "CARE-2",
            "is_active": True,
        },
    )
    db.insert_one(
        "residents",
        {
            "resident_id": "RES-1",
            "full_name": "A Resident",
            "room_id": "ROOM-1",
            "facility_id": "FAC-1",
        },
    )
    for caretaker_id, name in (("CARE-1", "Primary Carer"), ("CARE-2", "Backup Carer")):
        db.insert_one(
            "local_caretakers",
            {
                "caretaker_id": caretaker_id,
                "full_name": name,
                "facility_id": "FAC-1",
                "room_id": "ROOM-1",
                "availability": CareAvailability.AVAILABLE.value,
                "is_active": True,
                "email": f"{caretaker_id.lower()}@example.test",
            },
        )


def _create_incident():
    return IncidentStateMachine.create_incident(
        incident_id="INC-CARE-1",
        camera_id="CAM-1",
        room_id="ROOM-1",
        event_type="FALL DETECTION",
        status="PENDING",
        resident_id="RES-1",
        resident_name="A Resident",
    )


def test_routes_to_local_backup_once_and_acceptance_stops_deadline(isolated_database):
    db = isolated_database
    _seed_room_team(db)
    _create_incident()

    routed = EmergencyRoutingService.route_incident("INC-CARE-1")
    assert routed["active_caretaker_id"] == "CARE-1"
    first_notifications = db.find("notifications", {"incident_id": "INC-CARE-1"})
    assert len(first_notifications) == 1
    assert first_notifications[0]["recipient_id"] == "CARE-1"

    EmergencyRoutingService.route_incident("INC-CARE-1")
    assert len(db.find("notifications", {"incident_id": "INC-CARE-1"})) == 1

    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.update_one(
        "incidents",
        {"incident_id": "INC-CARE-1"},
        {"response_deadline_at": expired_at.isoformat()},
    )
    escalated = CaregiverNotificationService.process_overdue_escalations(
        now=datetime.now(timezone.utc)
    )
    assert escalated == ["INC-CARE-1"]
    incident = db.find_one("incidents", {"incident_id": "INC-CARE-1"})
    assert incident["active_caretaker_id"] == "CARE-2"
    assert len(db.find("notifications", {"incident_id": "INC-CARE-1"})) == 2

    updated = record_incident_action(
        "INC-CARE-1",
        "ACCEPTED",
        "ACKNOWLEDGED",
        {
            "user_id": "CARE-2",
            "username": "backup",
            "display_name": "Backup Carer",
            "role": "local_caretaker",
            "caretaker_id": "CARE-2",
        },
    )
    assert updated["status"] == "ACKNOWLEDGED"
    assert updated["response_deadline_at"] is None
    assert db.find("emergency_timeline", {"incident_id": "INC-CARE-1"})[0]["action"] == "ACCEPTED"


def test_unable_to_attend_immediately_escalates_to_backup(isolated_database):
    db = isolated_database
    _seed_room_team(db)
    _create_incident()
    EmergencyRoutingService.route_incident("INC-CARE-1")

    primary = {
        "user_id": "CARE-1",
        "username": "primary",
        "display_name": "Primary Carer",
        "role": "local_caretaker",
        "caretaker_id": "CARE-1",
    }
    record_incident_action(
        "INC-CARE-1",
        "UNABLE_TO_ATTEND",
        "ESCALATED_LOCAL_CARETAKER",
        primary,
    )
    CaregiverNotificationService.process_overdue_escalations()

    incident = db.find_one("incidents", {"incident_id": "INC-CARE-1"})
    assert incident["active_caretaker_id"] == "CARE-2"
    assert len(db.find("notifications", {"incident_id": "INC-CARE-1"})) == 2


def test_unassigned_caretaker_cannot_access_incident(isolated_database):
    db = isolated_database
    _seed_room_team(db)
    _create_incident()
    EmergencyRoutingService.route_incident("INC-CARE-1")

    with pytest.raises(HTTPException) as error:
        get_authorized_incident(
            "INC-CARE-1",
            {"role": "local_caretaker", "caretaker_id": "CARE-3"},
        )
    assert error.value.status_code == 403


def test_remote_responder_escalation_notifies_each_tier_and_stops_at_admin(isolated_database):
    db = isolated_database
    IncidentStateMachine.create_incident(
        incident_id="INC-REMOTE-1",
        camera_id="CAM-UNKNOWN",
        room_id="Unregistered Room",
        event_type="Manual SOS Emergency",
        status="PENDING",
        resident_id="RES-REMOTE",
        resident_name="Remote Resident",
    )

    routed = EmergencyRoutingService.route_incident("INC-REMOTE-1")
    assert routed["status"] == "ESCALATED_CARETAKER_1"
    assert len(db.find("notifications", {"incident_id": "INC-REMOTE-1"})) == 1

    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.update_one("incidents", {"incident_id": "INC-REMOTE-1"}, {"response_deadline_at": expired_at.isoformat()})
    CaregiverNotificationService.process_overdue_escalations()
    incident = db.find_one("incidents", {"incident_id": "INC-REMOTE-1"})
    assert incident["status"] == "ESCALATED_CARETAKER_2"
    assert len(db.find("notifications", {"incident_id": "INC-REMOTE-1"})) == 2

    db.update_one("incidents", {"incident_id": "INC-REMOTE-1"}, {"response_deadline_at": expired_at.isoformat()})
    CaregiverNotificationService.process_overdue_escalations()
    incident = db.find_one("incidents", {"incident_id": "INC-REMOTE-1"})
    assert incident["status"] == "UNACKNOWLEDGED_ADMIN_REQUIRED"
    assert incident["response_deadline_at"] is None
    assert len(db.find("notifications", {"incident_id": "INC-REMOTE-1"})) == 3
    assert not CaregiverNotificationService.process_overdue_escalations()


def test_admin_registration_hashes_credentials_and_links_records(isolated_database):
    db = isolated_database
    facility = register_facility(
        FacilityCreate(
            name="North Care",
            facility_type=FacilityType.OLD_AGE_HOME,
        )
    )
    room = register_room(
        RoomCreate(
            facility_id=facility["facility_id"],
            building="Main",
            floor="Ground",
            room_number="101",
            camera_id="CAM-1",
        )
    )
    resident = register_resident(
        ResidentCreate(
            full_name="A Resident",
            age=72,
            facility_id=facility["facility_id"],
            room_id=room["room_id"],
            emergency_contact="Relative, 555-0101",
            username="resident01",
            password="resident-password-1",
        )
    )
    caretaker = register_local_caretaker(
        LocalCaretakerCreate(
            full_name="Local Nurse",
            phone_number="555-0102",
            email="nurse@example.test",
            username="nurse01",
            password="caretaker-password-1",
            facility_id=facility["facility_id"],
            building="Main",
            floor="Ground",
            room_id=room["room_id"],
        )
    )

    stored_resident_user = db.find_one("users", {"username": "resident01"})
    stored_caretaker_user = db.find_one("users", {"username": "nurse01"})
    assert resident["resident_id"] == db.find_one("rooms", {"room_id": room["room_id"]})["resident_id"]
    assert caretaker.caretaker_id == db.find_one("rooms", {"room_id": room["room_id"]})["assigned_caretaker_id"]
    assert stored_resident_user["password_hash"] != "resident-password-1"
    assert stored_caretaker_user["password_hash"] != "caretaker-password-1"
    assert "password_hash" not in resident
    assert "password_hash" not in caretaker.model_dump()
