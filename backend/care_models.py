"""Validated request models for facility and care-team management."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FacilityType(str, Enum):
    OLD_AGE_HOME = "Old Age Home"
    HOSPITAL = "Hospital"
    REHABILITATION_CENTRE = "Rehabilitation Centre"
    HOME_BASED_CARE = "Home-Based Elderly Care"


class CareAvailability(str, Enum):
    AVAILABLE = "Available"
    BUSY = "Busy"
    ON_LEAVE = "On Leave"
    OFFLINE = "Offline"


class FacilityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    facility_type: FacilityType
    address: Optional[str] = Field(default=None, max_length=300)
    buildings: list[str] = Field(default_factory=list, max_length=100)
    floors: list[str] = Field(default_factory=list, max_length=200)


class FacilityResponse(FacilityCreate):
    facility_id: str
    created_at: str


class RoomCreate(BaseModel):
    facility_id: str = Field(min_length=1, max_length=80)
    building: str = Field(min_length=1, max_length=100)
    floor: str = Field(min_length=1, max_length=100)
    room_number: str = Field(min_length=1, max_length=40)
    camera_id: Optional[str] = Field(default=None, max_length=100)
    resident_id: Optional[str] = Field(default=None, max_length=80)
    assigned_caretaker_id: Optional[str] = Field(default=None, max_length=80)
    backup_caretaker_id: Optional[str] = Field(default=None, max_length=80)


class RoomResponse(RoomCreate):
    room_id: str
    created_at: str


class ResidentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=1, le=125)
    facility_id: str = Field(min_length=1, max_length=80)
    room_id: str = Field(min_length=1, max_length=80)
    emergency_contact: str = Field(min_length=3, max_length=160)
    assigned_caretaker_id: Optional[str] = Field(default=None, max_length=80)
    medical_assistance_notes: Optional[str] = Field(default=None, max_length=500)
    username: Optional[str] = Field(default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: Optional[str] = Field(default=None, min_length=12, max_length=128)


class ResidentResponse(BaseModel):
    resident_id: str
    full_name: str
    age: int
    facility_id: str
    room_id: str
    emergency_contact: str
    assigned_caretaker_id: Optional[str] = None
    medical_assistance_notes: Optional[str] = None
    created_at: str


class LocalCaretakerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone_number: str = Field(min_length=5, max_length=32)
    email: str = Field(min_length=3, max_length=254)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)
    facility_id: str = Field(min_length=1, max_length=80)
    building: str = Field(min_length=1, max_length=100)
    floor: str = Field(min_length=1, max_length=100)
    room_id: str = Field(min_length=1, max_length=80)
    availability: CareAvailability = CareAvailability.AVAILABLE
    backup_caretaker_id: Optional[str] = Field(default=None, max_length=80)


class LocalCaretakerUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone_number: Optional[str] = Field(default=None, min_length=5, max_length=32)
    email: Optional[str] = Field(default=None, min_length=3, max_length=254)
    facility_id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    building: Optional[str] = Field(default=None, min_length=1, max_length=100)
    floor: Optional[str] = Field(default=None, min_length=1, max_length=100)
    room_id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    availability: Optional[CareAvailability] = None
    backup_caretaker_id: Optional[str] = Field(default=None, max_length=80)
    is_active: Optional[bool] = None


class LocalCaretakerResponse(BaseModel):
    caretaker_id: str
    full_name: str
    phone_number: str
    email: str
    username: str
    facility_id: str
    building: str
    floor: str
    room_id: str
    availability: CareAvailability
    backup_caretaker_id: Optional[str] = None
    is_active: bool
    created_at: str


class AvailabilityUpdate(BaseModel):
    availability: CareAvailability


class AssignmentRequest(BaseModel):
    caretaker_id: Optional[str] = Field(default=None, max_length=80)
    backup_caretaker_id: Optional[str] = Field(default=None, max_length=80)
    remarks: Optional[str] = Field(default=None, max_length=500)


class EmergencyActionRequest(BaseModel):
    remarks: Optional[str] = Field(default=None, max_length=500)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
