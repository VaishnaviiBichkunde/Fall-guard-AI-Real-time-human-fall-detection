"""
FastAPI Router for Caregiver Management and Notifications.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from backend.database import db_manager
from backend.models import CaregiverCreate, CaregiverResponse
from backend.security import require_roles
from utils.notification_service import CaregiverNotificationService

router = APIRouter(prefix="/api/caregivers", tags=["Caregivers"])


@router.get("", response_model=List[CaregiverResponse], dependencies=[Depends(require_roles("admin", "caretaker_1", "caretaker_2", "local_caretaker"))])
def get_caregivers():
    """Retrieve all registered caregivers."""
    contacts = db_manager.find("caregivers")
    if not contacts:
        # Default seeding if empty
        defaults = [
            {"name": "Mohini Ravat", "email": "mohini.ravat@fallguard.local", "role": "Primary Caretaker (Caretaker 1)", "phone": "+91 98765 43210", "is_active": True, "is_available": True, "preferred_method": "EMAIL"},
            {"name": "Radha Raghav", "email": "radha.raghav@fallguard.local", "role": "Secondary Caretaker (Caretaker 2)", "phone": "+91 98123 45678", "is_active": True, "is_available": True, "preferred_method": "EMAIL"},
        ]
        for c in defaults:
            db_manager.insert_one("caregivers", c)
        return defaults
    return contacts


@router.post("", response_model=CaregiverResponse, dependencies=[Depends(require_roles("admin"))])
def add_caregiver(caregiver: CaregiverCreate):
    """Add a new emergency contact / caregiver."""
    existing = db_manager.find_one("caregivers", {"email": caregiver.email})
    if existing:
        raise HTTPException(status_code=400, detail="Caregiver with this email already registered.")

    doc = caregiver.model_dump()
    db_manager.insert_one("caregivers", doc)
    return doc


@router.post("/test-notification", dependencies=[Depends(require_roles("admin"))])
def send_test_notification():
    """Send a test email alert and return truthful status."""
    result = CaregiverNotificationService.send_test_alert()
    return result


@router.delete("/{email}", dependencies=[Depends(require_roles("admin"))])
def delete_caregiver(email: str):
    """Remove a caregiver by email."""
    deleted = db_manager.delete_one("caregivers", {"email": email})
    if not deleted:
        raise HTTPException(status_code=404, detail="Caregiver not found.")
    return {"status": "success", "message": f"Caregiver {email} removed."}
