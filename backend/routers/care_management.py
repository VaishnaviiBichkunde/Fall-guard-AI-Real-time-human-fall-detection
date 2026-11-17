"""Facility, resident, local-caretaker, and emergency workflow endpoints."""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.care_models import (
    AssignmentRequest,
    AvailabilityUpdate,
    CareAvailability,
    EmergencyActionRequest,
    FacilityCreate,
    FacilityResponse,
    LocalCaretakerCreate,
    LocalCaretakerResponse,
    LocalCaretakerUpdate,
    ResidentCreate,
    ResidentResponse,
    RoomCreate,
    RoomResponse,
)
from backend.database import db_manager
from backend.security import get_current_user, hash_password, require_roles
from utils.notification_service import CaregiverNotificationService
from backend.emergency_workflow import (
    assign_local_caretaker,
    get_authorized_incident,
    record_incident_action,
)

router = APIRouter(tags=["Care Management"])
admin_only = Depends(require_roles("admin"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def _facility_name(facility_id: str) -> str:
    facility = db_manager.find_one("facilities", {"facility_id": facility_id})
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found.")
    return facility["name"]


def _room(room_id: str) -> Dict[str, Any]:
    room = db_manager.find_one("rooms", {"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")
    return room


def _caretaker(caretaker_id: str) -> Dict[str, Any]:
    caretaker = db_manager.find_one("local_caretakers", {"caretaker_id": caretaker_id})
    if not caretaker or not caretaker.get("is_active", True):
        raise HTTPException(status_code=404, detail="Active local caretaker not found.")
    return caretaker


def _caretaker_response(record: Dict[str, Any]) -> LocalCaretakerResponse:
    return LocalCaretakerResponse.model_validate(record)


def _incident_for_actor(incident_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    return get_authorized_incident(incident_id, actor)


@router.post("/facilities/register", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_only])
def register_facility(payload: FacilityCreate):
    facility_id = _new_id("FAC")
    created_at = _now()
    document = {
        **payload.model_dump(),
        "facility_id": facility_id,
        "created_at": created_at,
        "is_active": True,
    }
    db_manager.insert_one("facilities", document)
    return document


@router.get("/facilities", response_model=List[FacilityResponse])
def get_facilities(actor=Depends(get_current_user)):
    if actor.get("role") not in {"admin", "local_caretaker", "caretaker_1", "caretaker_2"}:
        raise HTTPException(status_code=403, detail="Your account cannot view facility records.")
    if actor.get("role") == "local_caretaker":
        return db_manager.find(
            "facilities",
            {"facility_id": actor.get("facility_id"), "is_active": True},
            limit=1,
        )
    return db_manager.find("facilities", {"is_active": True}, limit=500)


@router.post("/rooms/register", response_model=RoomResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_only])
def register_room(payload: RoomCreate):
    _facility_name(payload.facility_id)
    if payload.resident_id or payload.assigned_caretaker_id or payload.backup_caretaker_id:
        raise HTTPException(
            status_code=400,
            detail="Create the room first, then register residents and assign caretakers.",
        )
    duplicate = db_manager.find_one(
        "rooms",
        {
            "facility_id": payload.facility_id,
            "building": payload.building,
            "floor": payload.floor,
            "room_number": payload.room_number,
        },
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This room is already registered in the facility.")
    if payload.camera_id and db_manager.find_one("rooms", {"camera_id": payload.camera_id}):
        raise HTTPException(status_code=409, detail="This camera is already assigned to a room.")
    document = {
        **payload.model_dump(),
        "room_id": _new_id("ROOM"),
        "created_at": _now(),
        "is_active": True,
    }
    db_manager.insert_one("rooms", document)
    return document


@router.get("/rooms", response_model=List[RoomResponse])
def get_rooms(
    facility_id: Optional[str] = None,
    actor=Depends(get_current_user),
):
    if actor.get("role") not in {"admin", "local_caretaker", "caretaker_1", "caretaker_2"}:
        raise HTTPException(status_code=403, detail="Your account cannot view room records.")
    query: Dict[str, Any] = {"is_active": True}
    if facility_id:
        query["facility_id"] = facility_id
    rooms = db_manager.find("rooms", query, limit=1000)
    if actor.get("role") == "local_caretaker":
        caretaker_id = actor.get("caretaker_id")
        rooms = [
            room for room in rooms
            if caretaker_id in {
                room.get("assigned_caretaker_id"),
                room.get("backup_caretaker_id"),
            }
        ]
    return rooms


@router.put("/rooms/{room_id}/assignment", dependencies=[admin_only])
def assign_room(
    room_id: str,
    payload: AssignmentRequest,
):
    room = _room(room_id)
    update: Dict[str, Any] = {}
    if "caretaker_id" in payload.model_fields_set:
        if not payload.caretaker_id:
            update["assigned_caretaker_id"] = None
        else:
            caretaker = _caretaker(payload.caretaker_id)
            if caretaker["room_id"] != room_id:
                raise HTTPException(status_code=400, detail="Caretaker must be assigned to this room.")
            update["assigned_caretaker_id"] = caretaker["caretaker_id"]
    if "backup_caretaker_id" in payload.model_fields_set:
        if not payload.backup_caretaker_id:
            update["backup_caretaker_id"] = None
        else:
            backup = _caretaker(payload.backup_caretaker_id)
            if backup["room_id"] != room_id:
                raise HTTPException(status_code=400, detail="Backup caretaker must be assigned to this room.")
            if backup["caretaker_id"] == update.get(
                "assigned_caretaker_id",
                room.get("assigned_caretaker_id"),
            ):
                raise HTTPException(status_code=400, detail="Primary and backup caretakers must be different.")
            update["backup_caretaker_id"] = backup["caretaker_id"]
    if payload.remarks is not None:
        update["assignment_remarks"] = payload.remarks
    db_manager.update_one("rooms", {"room_id": room_id}, update)
    room.update(update)
    return room


@router.post("/residents/register", response_model=ResidentResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_only])
def register_resident(payload: ResidentCreate):
    room = _room(payload.room_id)
    if room["facility_id"] != payload.facility_id:
        raise HTTPException(status_code=400, detail="Resident facility must match the room facility.")
    if room.get("resident_id"):
        raise HTTPException(status_code=409, detail="This room already has a resident assigned.")
    assigned_caretaker_id = payload.assigned_caretaker_id or room.get("assigned_caretaker_id")
    if payload.assigned_caretaker_id:
        caretaker = _caretaker(payload.assigned_caretaker_id)
        if caretaker["room_id"] != payload.room_id:
            raise HTTPException(status_code=400, detail="Assigned caretaker must be registered for this room.")
    username = payload.username.strip().lower() if payload.username else None
    if username and db_manager.find_one("users", {"username": username}):
        raise HTTPException(status_code=409, detail="This username is already registered.")
    if bool(username) != bool(payload.password):
        raise HTTPException(status_code=422, detail="Provide both resident username and password, or neither.")

    resident_id = _new_id("RES")
    document = payload.model_dump(exclude={"username", "password"})
    document.update(
        {
            "resident_id": resident_id,
            "assigned_caretaker_id": assigned_caretaker_id,
            "created_at": _now(),
            "is_active": True,
        }
    )
    db_manager.insert_one("residents", document)
    db_manager.update_one("rooms", {"room_id": payload.room_id}, {"resident_id": resident_id})
    if username and payload.password:
        db_manager.insert_one(
            "users",
            {
                "user_id": _new_id("USR"),
                "username": username,
                "display_name": payload.full_name,
                "role": "resident",
                "resident_id": resident_id,
                "password_hash": hash_password(payload.password),
                "is_active": True,
                "created_at": _now(),
            },
        )
    return document


@router.get("/residents", response_model=List[ResidentResponse])
def get_residents(
    facility_id: Optional[str] = None,
    actor=Depends(get_current_user),
):
    role = actor.get("role")
    if role not in {"admin", "local_caretaker", "caretaker_1", "caretaker_2"}:
        raise HTTPException(status_code=403, detail="Your account cannot list residents.")
    query: Dict[str, Any] = {"is_active": True}
    if facility_id:
        query["facility_id"] = facility_id
    if role == "local_caretaker":
        caretaker = _caretaker(actor["caretaker_id"])
        query["room_id"] = caretaker["room_id"]
    return db_manager.find("residents", query, limit=1000)


@router.get("/residents/me", response_model=ResidentResponse)
def get_my_resident_record(actor=Depends(require_roles("resident", "user"))):
    resident_id = actor.get("resident_id")
    resident = db_manager.find_one("residents", {"resident_id": resident_id}) if resident_id else None
    if not resident:
        raise HTTPException(status_code=404, detail="Resident profile not found.")
    return resident


@router.post("/caretakers/register", response_model=LocalCaretakerResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_only])
def register_local_caretaker(payload: LocalCaretakerCreate):
    facility = db_manager.find_one("facilities", {"facility_id": payload.facility_id, "is_active": True})
    if not facility:
        raise HTTPException(status_code=404, detail="Active facility not found.")
    room = _room(payload.room_id)
    if room["facility_id"] != payload.facility_id:
        raise HTTPException(status_code=400, detail="Caretaker facility must match the assigned room.")
    existing_primary = room.get("assigned_caretaker_id")
    if existing_primary and room.get("backup_caretaker_id"):
        raise HTTPException(
            status_code=409,
            detail="This room already has primary and backup caretakers assigned.",
        )
    username = payload.username.strip().lower()
    if db_manager.find_one("users", {"username": username}) or db_manager.find_one("local_caretakers", {"username": username}):
        raise HTTPException(status_code=409, detail="This username is already registered.")
    email = payload.email.strip().lower()
    if db_manager.find_one("local_caretakers", {"email": email}) or db_manager.find_one("users", {"email": email}):
        raise HTTPException(status_code=409, detail="This email is already registered.")
    if payload.backup_caretaker_id:
        backup = _caretaker(payload.backup_caretaker_id)
        if backup["room_id"] != payload.room_id or backup["facility_id"] != payload.facility_id:
            raise HTTPException(
                status_code=400,
                detail="Backup caretaker must belong to the same facility and room.",
            )
        if existing_primary:
            raise HTTPException(
                status_code=400,
                detail="Set the room's primary and backup assignments after caretaker registration.",
            )

    caretaker_id = _new_id("CARE")
    document = payload.model_dump(exclude={"password"})
    document.update(
        {
            "caretaker_id": caretaker_id,
            "username": username,
            "email": email,
            "password_hash": hash_password(payload.password),
            "is_active": True,
            "created_at": _now(),
        }
    )
    db_manager.insert_one("local_caretakers", document)
    designation = {
        "Hospital": "Nurse/Healthcare Staff",
        "Old Age Home": "Local Caretaker",
        "Rehabilitation Centre": "Rehabilitation Staff",
        "Home-Based Elderly Care": "Local Caretaker",
    }[facility["facility_type"]]
    db_manager.insert_one(
        "users",
        {
            "user_id": caretaker_id,
            "username": username,
            "display_name": payload.full_name,
            "role": "local_caretaker",
            "caretaker_id": caretaker_id,
            "facility_id": payload.facility_id,
            "designation": designation,
            "email": email,
            "password_hash": document["password_hash"],
            "is_active": True,
            "created_at": document["created_at"],
        },
    )
    if existing_primary and existing_primary != caretaker_id:
        db_manager.update_one(
            "rooms",
            {"room_id": payload.room_id},
            {"backup_caretaker_id": caretaker_id},
        )
    else:
        db_manager.update_one(
            "rooms",
            {"room_id": payload.room_id},
            {
                "assigned_caretaker_id": caretaker_id,
                "backup_caretaker_id": payload.backup_caretaker_id,
            },
        )
    return _caretaker_response(document)


@router.get("/caretakers", response_model=List[LocalCaretakerResponse])
def get_local_caretakers(actor=Depends(get_current_user)):
    if actor.get("role") == "admin":
        records = db_manager.find("local_caretakers", {"is_active": True}, limit=1000)
    elif actor.get("role") == "local_caretaker":
        records = db_manager.find("local_caretakers", {"caretaker_id": actor.get("caretaker_id")}, limit=1)
    else:
        raise HTTPException(status_code=403, detail="Your account cannot view local caretaker records.")
    return [_caretaker_response(record) for record in records]


@router.patch("/caretakers/{caretaker_id}", response_model=LocalCaretakerResponse, dependencies=[admin_only])
def update_local_caretaker(caretaker_id: str, payload: LocalCaretakerUpdate):
    caretaker = _caretaker(caretaker_id)
    update = payload.model_dump(exclude_unset=True)
    if "room_id" in update or "facility_id" in update:
        target_room = _room(update.get("room_id", caretaker["room_id"]))
        if target_room["facility_id"] != update.get("facility_id", caretaker["facility_id"]):
            raise HTTPException(status_code=400, detail="Caretaker facility must match the assigned room.")
    target_room_assignment: Dict[str, Any] = {}
    if "room_id" in update and update["room_id"] != caretaker["room_id"]:
        target_room = _room(update["room_id"])
        if caretaker_id not in {
            target_room.get("assigned_caretaker_id"),
            target_room.get("backup_caretaker_id"),
        }:
            if not target_room.get("assigned_caretaker_id"):
                target_room_assignment["assigned_caretaker_id"] = caretaker_id
            elif not target_room.get("backup_caretaker_id"):
                target_room_assignment["backup_caretaker_id"] = caretaker_id
            else:
                raise HTTPException(
                    status_code=409,
                    detail="The target room already has primary and backup caretakers.",
                )
    if "email" in update:
        update["email"] = update["email"].strip().lower()
        duplicate = db_manager.find_one("local_caretakers", {"email": update["email"]})
        duplicate_user = db_manager.find_one("users", {"email": update["email"]})
        if (
            (duplicate and duplicate.get("caretaker_id") != caretaker_id)
            or (duplicate_user and duplicate_user.get("user_id") != caretaker_id)
        ):
            raise HTTPException(status_code=409, detail="This email is already registered.")
    if "backup_caretaker_id" in update and update["backup_caretaker_id"]:
        if update["backup_caretaker_id"] == caretaker_id:
            raise HTTPException(status_code=400, detail="A caretaker cannot be their own backup.")
        _caretaker(update["backup_caretaker_id"])
    old_room_id = caretaker["room_id"]
    db_manager.update_one("local_caretakers", {"caretaker_id": caretaker_id}, update)
    caretaker.update(update)
    user_update = {}
    if "full_name" in update:
        user_update["display_name"] = update["full_name"]
    if "facility_id" in update:
        user_update["facility_id"] = update["facility_id"]
    if "email" in update:
        user_update["email"] = update["email"]
    if user_update:
        db_manager.update_one("users", {"user_id": caretaker_id}, user_update)
    if update.get("is_active") is False:
        db_manager.update_one("users", {"user_id": caretaker_id}, {"is_active": False})
    if "room_id" in update and update["room_id"] != old_room_id:
        old_room = db_manager.find_one("rooms", {"room_id": old_room_id})
        if old_room and old_room.get("assigned_caretaker_id") == caretaker_id:
            db_manager.update_one(
                "rooms",
                {"room_id": old_room_id},
                {"assigned_caretaker_id": None},
            )
        if old_room and old_room.get("backup_caretaker_id") == caretaker_id:
            db_manager.update_one(
                "rooms",
                {"room_id": old_room_id},
                {"backup_caretaker_id": None},
            )
        if target_room_assignment:
            db_manager.update_one("rooms", {"room_id": update["room_id"]}, target_room_assignment)
    return _caretaker_response(caretaker)


@router.delete("/caretakers/{caretaker_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[admin_only])
def deactivate_local_caretaker(caretaker_id: str):
    caretaker = _caretaker(caretaker_id)
    db_manager.update_one("local_caretakers", {"caretaker_id": caretaker_id}, {"is_active": False})
    db_manager.update_one("users", {"user_id": caretaker_id}, {"is_active": False})
    room = db_manager.find_one("rooms", {"room_id": caretaker["room_id"]})
    if room and room.get("assigned_caretaker_id") == caretaker_id:
        db_manager.update_one(
            "rooms",
            {"room_id": caretaker["room_id"]},
            {"assigned_caretaker_id": None},
        )
    if room and room.get("backup_caretaker_id") == caretaker_id:
        db_manager.update_one(
            "rooms",
            {"room_id": caretaker["room_id"]},
            {"backup_caretaker_id": None},
        )


@router.put("/caretakers/{caretaker_id}/availability")
def update_caretaker_availability(
    caretaker_id: str,
    payload: AvailabilityUpdate,
    actor=Depends(get_current_user),
):
    if actor.get("role") != "admin" and (
        actor.get("role") != "local_caretaker" or actor.get("caretaker_id") != caretaker_id
    ):
        raise HTTPException(status_code=403, detail="You can only change your own availability.")
    caretaker = _caretaker(caretaker_id)
    db_manager.update_one(
        "local_caretakers",
        {"caretaker_id": caretaker_id},
        {"availability": payload.availability.value},
    )
    caretaker["availability"] = payload.availability.value
    return _caretaker_response(caretaker)


@router.get("/caretakers/me/rooms")
def get_my_rooms(actor=Depends(require_roles("local_caretaker"))):
    caretaker_id = actor["caretaker_id"]
    return [
        room for room in db_manager.find("rooms", {"is_active": True}, limit=500)
        if caretaker_id in {room.get("assigned_caretaker_id"), room.get("backup_caretaker_id")}
    ]


@router.get("/caretakers/{caretaker_id}/incidents")
def get_caretaker_incidents(caretaker_id: str, actor=Depends(get_current_user)):
    if actor.get("role") != "admin" and (
        actor.get("role") != "local_caretaker"
        or actor.get("caretaker_id") != caretaker_id
    ):
        raise HTTPException(status_code=403, detail="You can only view your own incident history.")
    if actor.get("role") == "admin":
        return db_manager.find("incidents", limit=1000)
    assignments = db_manager.find("caretaker_assignments", {"caretaker_id": caretaker_id}, limit=500)
    incident_ids = {item["incident_id"] for item in assignments if item.get("incident_id")}
    return [
        incident
        for incident in db_manager.find("incidents", limit=1000)
        if incident.get("incident_id") in incident_ids
    ]


@router.post("/incidents/{incident_id}/assign", dependencies=[admin_only])
def assign_incident(incident_id: str, payload: AssignmentRequest):
    incident = db_manager.find_one("incidents", {"incident_id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    caretaker = _caretaker(payload.caretaker_id) if payload.caretaker_id else None
    if caretaker and caretaker.get("availability") != CareAvailability.AVAILABLE.value:
        raise HTTPException(status_code=409, detail="Selected caretaker is not available.")
    if not caretaker:
        room = db_manager.find_one("rooms", {"camera_id": incident.get("camera_id")})
        if not room and incident.get("room_id"):
            room = db_manager.find_one("rooms", {"room_number": incident["room_id"]})
        if room:
            assigned_id = room.get("assigned_caretaker_id")
            possible = db_manager.find_one("local_caretakers", {"caretaker_id": assigned_id}) if assigned_id else None
            caretaker = possible if possible and possible.get("availability") == CareAvailability.AVAILABLE.value else None
    if not caretaker:
        raise HTTPException(status_code=409, detail="No available local caretaker could be assigned.")
    _assign_incident_to_caretaker(incident, caretaker, {"role": "admin", "username": "admin", "display_name": "System Administrator"}, payload.remarks)
    return db_manager.find_one("incidents", {"incident_id": incident_id})


def _assign_incident_to_caretaker(
    incident: Dict[str, Any],
    caretaker: Dict[str, Any],
    actor: Dict[str, Any],
    remarks: Optional[str] = None,
) -> None:
    assign_local_caretaker(
        incident,
        caretaker,
        actor_name=actor.get("display_name", "System Administrator"),
        actor_id=actor.get("user_id", "admin"),
        remarks=remarks or "",
    )


def _perform_caretaker_action(
    incident_id: str,
    action: str,
    new_status: str,
    actor: Dict[str, Any],
    remarks: Optional[str],
) -> Dict[str, Any]:
    return record_incident_action(
        incident_id=incident_id,
        action=action,
        new_status=new_status,
        actor=actor,
        remarks=remarks or "",
    )


@router.post("/incidents/{incident_id}/accept")
def accept_incident(incident_id: str, payload: EmergencyActionRequest = EmergencyActionRequest(), actor=Depends(get_current_user)):
    return _perform_caretaker_action(incident_id, "ACCEPTED", "ACCEPTED", actor, payload.remarks)


@router.post("/incidents/{incident_id}/unable")
def unable_to_attend(incident_id: str, payload: EmergencyActionRequest = EmergencyActionRequest(), actor=Depends(get_current_user)):
    _perform_caretaker_action(incident_id, "UNABLE_TO_ATTEND", "ESCALATED", actor, payload.remarks)
    CaregiverNotificationService.process_overdue_escalations()
    return db_manager.find_one("incidents", {"incident_id": incident_id})


@router.post("/incidents/{incident_id}/on-the-way")
def mark_on_the_way(incident_id: str, payload: EmergencyActionRequest = EmergencyActionRequest(), actor=Depends(get_current_user)):
    return _perform_caretaker_action(incident_id, "ON_THE_WAY", "ON_THE_WAY", actor, payload.remarks)


@router.post("/incidents/{incident_id}/reached")
def mark_reached(incident_id: str, payload: EmergencyActionRequest = EmergencyActionRequest(), actor=Depends(get_current_user)):
    return _perform_caretaker_action(incident_id, "REACHED_LOCATION", "REACHED_LOCATION", actor, payload.remarks)


@router.post("/incidents/{incident_id}/assistance")
def mark_assistance_provided(incident_id: str, payload: EmergencyActionRequest = EmergencyActionRequest(), actor=Depends(get_current_user)):
    return _perform_caretaker_action(incident_id, "ASSISTANCE_PROVIDED", "ASSISTANCE_PROVIDED", actor, payload.remarks)


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, payload: EmergencyActionRequest = EmergencyActionRequest(), actor=Depends(get_current_user)):
    if actor.get("role") not in {"admin", "local_caretaker", "caretaker_1", "caretaker_2"}:
        raise HTTPException(status_code=403, detail="Only a responder or administrator can resolve incidents.")
    return record_incident_action(
        incident_id=incident_id,
        action="RESOLVED",
        new_status="RESOLVED",
        actor=actor,
        remarks=payload.remarks or "",
    )


@router.get("/incidents/{incident_id}/timeline")
def get_incident_timeline(incident_id: str, actor=Depends(get_current_user)):
    incident = _incident_for_actor(incident_id, actor)
    entries = db_manager.find("emergency_timeline", {"incident_id": incident_id}, limit=1000)
    return entries or incident.get("timeline", [])
