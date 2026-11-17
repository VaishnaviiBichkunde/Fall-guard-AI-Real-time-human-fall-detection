"""
Pydantic Request and Response Models for Fall Guard AI REST API.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentState(str, Enum):
    DETECTED = "DETECTED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACKNOWLEDGED_SAFE = "ACKNOWLEDGED_SAFE"
    HELP_REQUESTED = "HELP_REQUESTED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class IncidentCreate(BaseModel):
    incident_id: Optional[str] = Field(None, description="Unique incident identifier")
    camera_id: str = Field(default="CAM-001")
    room_id: str = Field(default="Living Room")
    event_type: str = Field(default="Possible Fall")
    detection_evidence: List[str] = Field(default_factory=list)
    body_angle_degrees: float = Field(default=0.0)
    status: IncidentState = Field(default=IncidentState.PENDING_VERIFICATION)


class IncidentResponse(BaseModel):
    incident_id: str
    camera_id: str
    room_id: str
    room_number: Optional[str] = None
    resident_id: Optional[str] = "RES-101"
    resident_name: Optional[str] = "Elderly Resident / Patient"
    detected_at: str
    original_emergency_timestamp: Optional[str] = None
    event_type: str = "Possible Fall"
    emergency_type: Optional[str] = "Possible Fall"
    emergency_description: Optional[str] = None
    body_angle_degrees: float = 0.0
    detection_evidence: List[str] = Field(default_factory=list)
    verification_status: str = "PENDING_VERIFICATION"
    status: Optional[str] = "PENDING_VERIFICATION"
    current_assigned_caretaker: Optional[str] = "Mohini Ravat"
    user_response: str = "NONE"
    response_timestamp: Optional[str] = None
    acknowledgement_timestamp: Optional[str] = None
    acknowledged_by: Optional[str] = None
    escalation_timestamp: Optional[str] = None
    escalation_reason: Optional[str] = None
    resolution_timestamp: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    response_stage_started_at: Optional[str] = None
    response_deadline_at: Optional[str] = None
    notification_status: str = "NOT_CONFIGURED"
    caregiver_notification_status: Optional[str] = "NOT_CONFIGURED"
    closed_at: Optional[str] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    escalation_history: List[Dict[str, Any]] = Field(default_factory=list)


class VerificationAction(BaseModel):
    incident_id: str
    action: str = Field(..., description="'I_AM_OK' or 'NEED_HELP' or 'TIMEOUT'")
    response_source: str = Field(default="BUTTON", description="'BUTTON' or 'VOICE'")


class AcknowledgeAction(BaseModel):
    caretaker_name: Optional[str] = "Mohini Ravat"
    notes: Optional[str] = "Caretaker acknowledged emergency and is on-site."
    response_source: str = "BUTTON"


class CloseAction(BaseModel):
    reviewer: str = "Administrator"
    notes: str = "Incident resolved and verified."


class ResolveAction(BaseModel):
    resolved_by: str = "Mohini Ravat"
    notes: Optional[str] = "Resident assisted, vital signs stable."


class VoiceEmergencyRequest(BaseModel):
    phrase: str
    resident_id: Optional[str] = "RES-101"
    resident_name: Optional[str] = "Elderly Resident / Patient"
    room_id: Optional[str] = "Resident Room"


class CaregiverCreate(BaseModel):
    name: str
    email: str
    role: str = "Family Caregiver"
    phone: Optional[str] = None
    is_active: bool = True


class CaregiverResponse(CaregiverCreate):
    id: Optional[str] = None


class RoomConfig(BaseModel):
    room_id: str
    camera_id: str
    camera_index: int = 0
    is_active: bool = True
