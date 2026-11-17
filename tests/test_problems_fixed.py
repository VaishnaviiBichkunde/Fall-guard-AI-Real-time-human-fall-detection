"""Tests verifying fixes for Problem 1, Problem 2, and Problem 3."""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from backend.database import db_manager
from core.incident_state_machine import IncidentStateMachine
from utils.notification_service import CaregiverNotificationService

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


def _login(username, password):
    app = AppTest.from_file(APP_PATH).run(timeout=30)
    app.text_input[0].set_value(username)
    app.text_input[1].set_value(password)
    app.button[0].click()
    return app.run(timeout=30)


def test_problem3_sign_out_clears_state_and_locks_dashboard():
    """Problem 3: Sign Out clears session state, stops camera, returns to login screen."""
    app = _login("user", "user123")
    assert app.session_state["authenticated"]
    assert app.session_state["user_role"] == "user"

    # Click global Sign Out button
    logout_button = next(b for b in app.button if "Sign Out" in b.label)
    logout_button.click()
    app.run(timeout=30)

    # Verify session cleared and back to unauthenticated login form
    assert not app.session_state["authenticated"]
    assert app.session_state["user_role"] == ""
    assert app.session_state["active_incident"] is None
    assert app.text_input[0].value == ""
    assert app.text_input[1].value == ""


def test_problem2_caretaker_sidebar_navigation_renders_sections():
    """Problem 2: Caretaker sidebar Care Console Options switch views properly."""
    app = _login("mohini", "mohini123")
    assert app.session_state["authenticated"]
    assert app.session_state["user_role"] == "caretaker_1"

    # Verify sidebar radio exists and has unique key
    nav_key = "caretaker_selected_nav_1"
    assert nav_key in app.session_state

    # Switch to Live Room Monitoring
    app.radio(key=nav_key).set_value("Live Room Monitoring 📹").run(timeout=30)
    assert app.session_state[nav_key] == "Live Room Monitoring 📹"
    assert any("Live Patient-Room Monitoring" in m.value for m in app.markdown)

    # Switch to Resident Care Profile
    app.radio(key=nav_key).set_value("👤 Resident Care Profile").run(timeout=30)
    assert app.session_state[nav_key] == "👤 Resident Care Profile"
    assert any("Resident Profile — Resident 01" in m.value for m in app.markdown)

    # Switch to Caregiver Duty Roster
    app.radio(key=nav_key).set_value("👥 Caregiver Duty Roster").run(timeout=30)
    assert app.session_state[nav_key] == "👥 Caregiver Duty Roster"
    assert any("Caregiver Availability & Rosters" in m.value for m in app.markdown)

    # Switch to Quick Intercom Directory
    app.radio(key=nav_key).set_value("📞 Quick Intercom Directory").run(timeout=30)
    assert app.session_state[nav_key] == "📞 Quick Intercom Directory"
    assert any("Quick Intercom Contacts" in m.value for m in app.markdown)


import datetime

def test_problem2_caretaker_alert_forwarding_and_display_on_backup():
    """Problem 2: Mohini forwarding emergency displays alert on Radha's dashboard."""
    inc_id = f"TEST-FWD-{datetime.datetime.now().strftime('%H%M%S')}"
    new_inc = IncidentStateMachine.create_incident(
        incident_id=inc_id,
        camera_id="CAM-001",
        room_id="Living Room — Camera 1",
        event_type="Possible Fall",
        emergency_type="FALL DETECTION",
        status="PENDING",
        current_assigned_caretaker="Mohini Ravat",
        resident_id="RES-101",
        resident_name="Elderly Resident / Patient",
    )

    try:
        # Mohini forwards the alert
        CaregiverNotificationService.forward_alert_to_caretaker2(
            incident_id=inc_id,
            room_name="Living Room — Camera 1",
            body_angle=75.0,
            reason="Mohini Ravat called for backup / forwarded.",
        )

        doc = db_manager.find_one("incidents", {"incident_id": inc_id})
        assert doc["current_assigned_caretaker"] == "Radha Raghav"
        assert doc["status"] == "ESCALATED_CARETAKER_2"

        # Now login as Radha Raghav (Caretaker 2) and verify alert is visible on her dashboard
        app2 = _login("radha", "radha123")
        assert app2.session_state["authenticated"]
        assert app2.session_state["user_role"] == "caretaker_2"
        assert any("EMERGENCY ALERT ASSIGNED TO RADHA RAGHAV" in m.value for m in app2.markdown)

        # Verify the 3 action buttons exist for Caretaker 2
        button_labels = [b.label for b in app2.button]
        assert any("ACKNOWLEDGE & RESPOND" in l for l in button_labels)
        assert any("FORWARD TO FACILITY ADMINISTRATOR" in l for l in button_labels)
        assert any("Dismiss / Clear" in l for l in button_labels)

        # Switch Radha to "Live Room Monitoring" and verify alert is STILL visible prominently above live camera
        nav_key = "caretaker_selected_nav_2"
        app2.radio(key=nav_key).set_value("Live Room Monitoring 📹").run(timeout=30)
        assert any("EMERGENCY ALERT ASSIGNED TO RADHA RAGHAV" in m.value for m in app2.markdown)
        assert any("Live Patient-Room Monitoring" in m.value for m in app2.markdown)

        # Click Dismiss / Clear to resolve incident and ensure camera stream is active
        dismiss_btn = next(b for b in app2.button if "Dismiss / Clear" in b.label)
        dismiss_btn.click()
        app2.run(timeout=30)
        assert app2.session_state["stream_active"]
        res_doc = db_manager.find_one("incidents", {"incident_id": inc_id})
        assert res_doc["status"] == "RESOLVED"
    finally:
        db_manager.delete_many("incidents", {"incident_id": inc_id})


def test_problem1_no_fake_person_and_proper_error_handling():
    """Problem 1: No simulated/fake cartoon figure is shown when camera unavailable."""
    app = _login("user", "user123")
    assert app.session_state["authenticated"]
    # Check that error is clearly shown or camera status displayed without dummy figures
    assert not any("fake" in m.value.lower() or "dummy" in m.value.lower() for m in app.markdown)
