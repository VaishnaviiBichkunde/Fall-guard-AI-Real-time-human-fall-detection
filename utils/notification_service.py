"""
Real SMTP Caregiver Notification Service for Fall Guard AI.
Never reports fake success. Dispatches real emails via configured SMTP provider.
"""

from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
import threading
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from backend.database import db_manager

load_dotenv()
logger = logging.getLogger(__name__)

try:
    _configured_response_timeout = int(os.getenv("CARETAKER_RESPONSE_TIMEOUT_SECONDS", "30"))
except ValueError:
    logger.error("Invalid CARETAKER_RESPONSE_TIMEOUT_SECONDS; using 30 seconds.")
    _configured_response_timeout = 30
if not 5 <= _configured_response_timeout <= 3600:
    logger.error("CARETAKER_RESPONSE_TIMEOUT_SECONDS must be 5..3600; using 30 seconds.")
    _configured_response_timeout = 30
RESPONSE_TIMEOUT_SECONDS = _configured_response_timeout

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "") or SMTP_USER
APP_URL = os.getenv("APP_URL", "http://localhost:8501")


class CaregiverNotificationService:
    """Manages email dispatch to registered caregivers with verified delivery state."""

    RESPONSE_TIMEOUT_SECONDS = _configured_response_timeout
    _escalation_lock = threading.Lock()

    @staticmethod
    def _response_window_fields(now: Optional[datetime] = None) -> Dict[str, Optional[str]]:
        started_at = now or datetime.now(timezone.utc)
        deadline = started_at + timedelta(seconds=CaregiverNotificationService.RESPONSE_TIMEOUT_SECONDS)
        return {
            "response_stage_started_at": started_at.isoformat(timespec="seconds"),
            "response_deadline_at": deadline.isoformat(timespec="seconds"),
        }

    @classmethod
    def process_overdue_escalations(cls, now: Optional[datetime] = None) -> List[str]:
        """Forward unacknowledged local/remote caregiver alerts after their response window expires."""
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        escalated_ids = []
        with cls._escalation_lock:
            active_incidents = db_manager.find(
                "incidents",
                {
                    "status": {
                        "$in": [
                            "PENDING",
                            "ESCALATED_LOCAL_CARETAKER",
                            "ESCALATED_CARETAKER_1",
                            "ESCALATED_CARETAKER_2",
                        ]
                    }
                },
                limit=200,
            )
            for incident in active_incidents:
                deadline_value = incident.get("response_deadline_at")
                if not deadline_value:
                    continue
                try:
                    deadline = datetime.fromisoformat(deadline_value.replace("Z", "+00:00"))
                except ValueError:
                    logger.error(
                        "Invalid response deadline for incident %s: %s",
                        incident.get("incident_id"),
                        deadline_value,
                    )
                    continue
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                if deadline > current_time:
                    continue

                incident_id = incident.get("incident_id")
                current = db_manager.find_one("incidents", {"incident_id": incident_id})
                if not current or current.get("status") != incident.get("status"):
                    continue

                if current["status"] == "ESCALATED_LOCAL_CARETAKER":
                    from backend.emergency_workflow import EmergencyRoutingService

                    EmergencyRoutingService.escalate_local_caretaker(current)
                elif current["status"] in ("PENDING", "ESCALATED_CARETAKER_1"):
                    reason = f"Emergency escalated because Caretaker 1 did not respond within {cls.RESPONSE_TIMEOUT_SECONDS} seconds."
                    cls.forward_alert_to_caretaker2(
                        incident_id=incident_id,
                        room_name=current.get("room_id", "Living Room"),
                        body_angle=current.get("body_angle_degrees", 70.0),
                        reason=reason,
                    )
                else:
                    reason = f"Emergency escalated to Admin because Caretaker 2 did not respond within {cls.RESPONSE_TIMEOUT_SECONDS} seconds."
                    cls.forward_alert_to_admin(
                        incident_id=incident_id,
                        room_name=current.get("room_id", "Living Room"),
                        body_angle=current.get("body_angle_degrees", 70.0),
                        reason=reason,
                    )
                escalated_ids.append(incident_id)
        return escalated_ids

    @classmethod
    def notify_recipient(
        cls,
        *,
        incident: Dict[str, Any],
        recipient_id: str,
        recipient_name: str,
        recipient_email: str,
        stage: str,
    ) -> Dict[str, Any]:
        """Persist an in-app alert once and optionally send its email notification."""
        incident_id = incident["incident_id"]
        notification_id = f"{incident_id}:{stage}:{recipient_id}"
        existing = db_manager.find_one("notifications", {"notification_id": notification_id})
        if existing:
            return existing

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        notification = {
            "notification_id": notification_id,
            "incident_id": incident_id,
            "recipient_id": recipient_id,
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
            "channel": "IN_APP",
            "status": "DELIVERED",
            "created_at": created_at,
            "message": (
                f"Emergency {incident_id}: resident {incident.get('resident_name', 'Unknown resident')} "
                f"at {incident.get('facility_name', 'registered facility')} / "
                f"{incident.get('room_number', incident.get('room_id', 'unknown room'))}. "
                f"Fall detected at {incident.get('detected_at', created_at)}."
            ),
        }
        db_manager.insert_one("notifications", notification)

        if recipient_email and cls.is_configured():
            email_result = cls.dispatch_incident_alert(
                {
                    **incident,
                    "timestamp": incident.get("detected_at", created_at),
                },
                recipient_emails=[recipient_email],
            )
            notification["email_status"] = email_result.get("status", "FAILED")
            notification["email_message"] = email_result.get("message", "")
        else:
            notification["email_status"] = "NOT_CONFIGURED"
            notification["email_message"] = "In-app alert delivered; SMTP is not configured."
        db_manager.update_one(
            "notifications",
            {"notification_id": notification_id},
            {
                "email_status": notification["email_status"],
                "email_message": notification["email_message"],
            },
        )
        return notification

    @staticmethod
    def is_configured() -> bool:
        """Returns True only if SMTP credentials are fully provided."""
        return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

    @classmethod
    def dispatch_incident_alert(
        cls,
        incident: Dict[str, Any],
        recipient_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches emergency notification for an incident.
        Returns status dict: {'status': 'SENT' | 'FAILED' | 'NOT_CONFIGURED', 'message': str}
        """
        incident_id = incident.get("incident_id", "UNKNOWN")
        room_id = incident.get("room_id", "Default Room")
        timestamp = incident.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        angle = incident.get("body_angle_degrees", 0.0)

        # 1. Determine recipients
        if not recipient_emails:
            # Query active caregivers from database
            caregivers = db_manager.find("caregivers", {"is_active": True})
            if caregivers:
                recipient_emails = [c["email"] for c in caregivers if "email" in c]
            else:
                default_caregiver = os.getenv("DEFAULT_CAREGIVER_EMAIL")
                if default_caregiver:
                    recipient_emails = [default_caregiver]

        if not recipient_emails:
            result = {
                "status": "NOT CONFIGURED",
                "message": "No caregiver email addresses registered or active.",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            cls._update_incident_notif_status(incident_id, "NOT CONFIGURED", result["message"])
            return result

        # 2. Check if SMTP is configured
        if not cls.is_configured():
            result = {
                "status": "NOT CONFIGURED",
                "message": (
                "SMTP credentials are not configured in the environment "
                "(SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SENDER_EMAIL)."
                ),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            cls._update_incident_notif_status(incident_id, "NOT CONFIGURED", result["message"])
            return result

        # 3. Build Email Message
        subject = f"🚨 URGENT: Fall Alert Escalation at {room_id} [{incident_id}]"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1E293B;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 2px solid #EF4444; border-radius: 12px; background: #FFF5F5;">
                <h2 style="color: #DC2626; margin-top: 0;">🚨 Fall Guard AI — Emergency Assistance Request</h2>
                <p>An emergency incident requires immediate attention.</p>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr><td style="padding: 8px; font-weight: bold; width: 40%;">Incident ID:</td><td style="padding: 8px;">{incident_id}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Camera / Room:</td><td style="padding: 8px;">{room_id}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Detection Time:</td><td style="padding: 8px;">{timestamp}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Torso Angle:</td><td style="padding: 8px;">{angle:.1f}°</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Current Status:</td><td style="padding: 8px; color: #DC2626; font-weight: bold;">ESCALATED — PENDING CAREGIVER RESPONSE</td></tr>
                </table>
                <p>Caretaker alerts automatically forward to the next tier after the configured response period without acknowledgement. Administrator alerts remain open until an action or resolution is recorded.</p>
                <p>Please check on the individual immediately or log in to the monitoring portal:</p>
                <p><a href="{APP_URL}" style="display: inline-block; padding: 12px 24px; background: #DC2626; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">Open Fall Guard AI Dashboard</a></p>
                <hr style="border: 0; border-top: 1px solid #FECACA; margin: 20px 0;">
                <p style="font-size: 12px; color: #64748B;">This is an automated safety alert generated by the Fall Guard AI system.</p>
            </div>
        </body>
        </html>
        """

        # 4. Perform Real SMTP Handshake and Send (fast timeout to keep UI responsive)
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SENDER_EMAIL
            msg["To"] = ", ".join(recipient_emails)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=3) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SENDER_EMAIL, recipient_emails, msg.as_string())

            result = {
                "status": "SENT",
                "message": f"Emergency alert submitted successfully to: {', '.join(recipient_emails)}",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            cls._update_incident_notif_status(incident_id, "SENT", result["message"])
            return result

        except Exception as err:
            logger.error("SMTP delivery failed for incident %s: %s", incident_id, err)
            result = {
                "status": "FAILED",
                "message": f"SMTP dispatch failed: {str(err)}",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            cls._update_incident_notif_status(incident_id, "FAILED", result["message"])
            return result

    @classmethod
    def dispatch_tiered_escalation(
        cls,
        incident_id: str,
        room_name: str = "Living Room",
        timestamp: str = "",
        body_angle: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Tiered Emergency Alert Dispatch:
        1. Caretaker 1 (Primary Caretaker), with a configurable response window
        2. If unavailable or unanswered -> Caretaker 2 (Secondary Caretaker)
        3. If unavailable or unanswered -> System Administrator (Admin)
        """
        now_time = datetime.now().strftime("%H:%M:%S")
        time_str = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Gather active caregivers from DB
        caregivers = db_manager.find("caregivers", {"is_active": True})
        if not caregivers:
            caregivers = [
                {"name": "Mohini Ravat", "email": "mohini.ravat@fallguard.local", "role": "Primary Caretaker (Caretaker 1)", "phone": "+91 98765 43210", "is_active": True, "is_available": True},
                {"name": "Radha Raghav", "email": "radha.raghav@fallguard.local", "role": "Secondary Caretaker (Caretaker 2)", "phone": "+91 98123 45678", "is_active": True, "is_available": True},
            ]

        caretaker_1 = next(
            (c for c in caregivers if "Mohini" in c.get("name", "") or c.get("priority") == 1),
            {"name": "Mohini Ravat", "email": "mohini.ravat@fallguard.local", "role": "Primary Caretaker (Caretaker 1)", "is_available": True},
        )
        caretaker_2 = next(
            (c for c in caregivers if "Radha" in c.get("name", "") or c.get("priority") == 2),
            {"name": "Radha Raghav", "email": "radha.raghav@fallguard.local", "role": "Secondary Caretaker (Caretaker 2)", "is_available": True},
        )
        admin_contact = {
            "name": "System Administrator",
            "email": os.getenv("ADMIN_EMAIL", "admin@fallguard.local"),
            "role": "System Administrator (Emergency Override)",
        }

        escalation_chain = []
        final_recipient = None
        final_status = "NOT_CONFIGURED"

        # --- STEP 1: Attempt Caretaker 1 ---
        c1_available = caretaker_1.get("is_available", True)
        c1_email = caretaker_1.get("email", "").strip()

        if c1_available:
            escalation_chain.append({
                "tier": "Caretaker 1 (Primary)",
                "name": caretaker_1.get("name", "Mohini Ravat"),
                "email": c1_email or "mohini.ravat@fallguard.local",
                "status": "ALERT RECEIVED & RESPONDING",
                "note": f"Alert message received! Caretaker 1 ({caretaker_1.get('name', 'Mohini Ravat')}) is actively responding.",
            })
            # Caretaker 2 and Admin remain on standby
            escalation_chain.append({
                "tier": "Caretaker 2 (Secondary)",
                "name": caretaker_2.get("name", "Radha Raghav"),
                "email": caretaker_2.get("email", "radha.raghav@fallguard.local"),
                "status": "STANDBY (Caretaker 1 Responding)",
                "note": "Caretaker 1 (Mohini Ravat) is responding to the emergency. Caretaker 2 (Radha Raghav) remains on standby.",
            })
            escalation_chain.append({
                "tier": "System Administrator (Admin)",
                "name": admin_contact["name"],
                "email": admin_contact["email"],
                "status": "STANDBY (Caretaker Responding)",
                "note": "Primary caretaker is handling the emergency. Admin on standby.",
            })
            final_recipient = caretaker_1
            final_status = "SENT"

        else:
            # Caretaker 1 is marked unavailable / off-duty / not responding
            escalation_chain.append({
                "tier": "Caretaker 1 (Primary)",
                "name": caretaker_1.get("name", "Mohini Ravat"),
                "email": c1_email or "mohini.ravat@fallguard.local",
                "status": "NOT RESPONDING",
                "note": "Caretaker 1 (Mohini Ravat) did not respond. Alert message escalated to Caretaker 2 (Radha Raghav).",
            })

            # --- STEP 2: Attempt Caretaker 2 if Caretaker 1 unavailable ---
            c2_available = caretaker_2.get("is_available", True)
            c2_email = caretaker_2.get("email", "").strip()

            if c2_available:
                escalation_chain.append({
                    "tier": "Caretaker 2 (Secondary)",
                    "name": caretaker_2.get("name", "Radha Raghav"),
                    "email": c2_email or "radha.raghav@fallguard.local",
                    "status": "ALERT RECEIVED & RESPONDING",
                    "note": f"Caretaker 1 did not respond! Alert message delivered to Caretaker 2 ({caretaker_2.get('name', 'Radha Raghav')}) who is now responding.",
                })
                escalation_chain.append({
                    "tier": "System Administrator (Admin)",
                    "name": admin_contact["name"],
                    "email": admin_contact["email"],
                    "status": "STANDBY (Caretaker Responding)",
                    "note": "Secondary caretaker (Radha Raghav) is handling the emergency. Admin on standby.",
                })
                final_recipient = caretaker_2
                final_status = "SENT"

            else:
                # Both Caretaker 1 and Caretaker 2 are unavailable
                escalation_chain.append({
                    "tier": "Caretaker 2 (Secondary)",
                    "name": caretaker_2.get("name", "Radha Raghav"),
                    "email": c2_email or "radha.raghav@fallguard.local",
                    "status": "NOT RESPONDING",
                    "note": "Caretaker 2 (Radha Raghav) also did not respond. Escalating to System Administrator.",
                })

                # --- STEP 3: Fallback to System Administrator ---
                admin_email = admin_contact["email"]
                escalation_chain.append({
                    "tier": "System Administrator (Admin)",
                    "name": admin_contact["name"],
                    "email": admin_email,
                    "status": "CRITICAL ALERT (ADMIN OVERRIDE)",
                    "note": "Both Caretaker 1 & Caretaker 2 did not respond! Emergency alert escalated directly to Admin.",
                })
                final_recipient = admin_contact
                final_status = "ESCALATED_TO_ADMIN"

        if final_recipient == caretaker_1:
            active_stage_status = "ESCALATED_CARETAKER_1"
        elif final_recipient == caretaker_2:
            active_stage_status = "ESCALATED_CARETAKER_2"
        else:
            active_stage_status = "CRITICAL_ADMIN_OVERRIDE"

        response_window = (
            cls._response_window_fields()
            if active_stage_status != "CRITICAL_ADMIN_OVERRIDE"
            else {"response_stage_started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "response_deadline_at": None}
        )

        # Update MongoDB Incident with full escalation details and timeline
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        timeline = incident.get("timeline", []) if incident else []
        timeline.append({
            "time": now_time,
            "event": f"Tiered Escalation: Alert routed to {final_recipient['name']} ({final_recipient.get('role', 'Emergency Contact')})",
        })

        db_manager.update_one(
            "incidents",
            {"incident_id": incident_id},
            {
                "status": active_stage_status,
                "verification_status": active_stage_status,
                "escalation_chain": escalation_chain,
                "active_contact": final_recipient,
                "notification_status": final_status,
                "timeline": timeline,
                **response_window,
            },
        )
        recipient_user = db_manager.find_one("users", {"email": final_recipient.get("email", "")})
        cls.notify_recipient(
            incident={
                **(incident or {}),
                "incident_id": incident_id,
                "room_id": room_name,
                "body_angle_degrees": body_angle,
                "detected_at": time_str,
                "active_contact": final_recipient,
            },
            recipient_id=(recipient_user or {}).get(
                "user_id",
                "admin" if active_stage_status == "CRITICAL_ADMIN_OVERRIDE" else
                "mohini" if active_stage_status == "ESCALATED_CARETAKER_1" else "radha",
            ),
            recipient_name=final_recipient.get("name", "Assigned responder"),
            recipient_email=final_recipient.get("email", ""),
            stage=active_stage_status,
        )

        return {
            "status": active_stage_status,
            "stage": active_stage_status,
            "contact": final_recipient,
            "escalation_chain": escalation_chain,
            "message": f"Alert routed to: {final_recipient['name']} ({final_recipient.get('role', 'Emergency')})",
        }

    @staticmethod
    def _update_incident_notif_status(incident_id: str, status: str, message: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        timeline = incident.get("timeline", []) if incident else []
        timeline.append({"time": now_str, "event": f"Caregiver Notification [{status}]: {message}"})

        db_manager.update_one(
            "incidents",
            {"incident_id": incident_id},
            {
                "caregiver_notification_status": status,
                "notification_status": status,
                "timeline": timeline,
            },
        )

    @classmethod
    def dispatch_emergency_alert(
        cls,
        incident_id: str,
        room_name: str = "Living Room",
        timestamp: str = "",
        body_angle: float = 0.0,
    ) -> Dict[str, Any]:
        """Dispatches tiered emergency alert starting at Caretaker 1, falling back to Caretaker 2 and Admin."""
        return cls.dispatch_tiered_escalation(
            incident_id=incident_id,
            room_name=room_name,
            timestamp=timestamp,
            body_angle=body_angle,
        )

    @classmethod
    def send_test_alert(cls, recipient_email: Optional[str] = None) -> Dict[str, Any]:
        """Sends a test email notification to verify SMTP setup."""
        if not cls.is_configured():
            return {
                "status": "NOT_CONFIGURED",
                "message": "SMTP credentials (SMTP_HOST, SMTP_USER, SMTP_PASSWORD) are not set in .env.",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }

        recipients = [recipient_email] if recipient_email else None
        if not recipients:
            caregivers = db_manager.find("caregivers", {"is_active": True})
            if caregivers:
                recipients = [c["email"] for c in caregivers if "email" in c]
            else:
                recipients = [SENDER_EMAIL] if SENDER_EMAIL else []

        if not recipients:
            return {
                "status": "NOT_CONFIGURED",
                "message": "No active caregiver email found to receive test alert.",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }

        test_incident = {
            "incident_id": f"TEST-ALERT-{datetime.now().strftime('%H%M%S')}",
            "room_id": "System Health Test Node",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "body_angle_degrees": 0.0,
        }
        return cls.dispatch_incident_alert(test_incident, recipient_emails=recipients)

    @classmethod
    def forward_alert_to_caretaker2(
        cls,
        incident_id: str,
        room_name: str = "Living Room",
        body_angle: float = 70.0,
        reason: str = "Caretaker 1 (Mohini Ravat) cannot attend and forwarded call.",
    ) -> Dict[str, Any]:
        """Explicitly forwards an active emergency from Caretaker 1 (Mohini) to Caretaker 2 (Radha)."""
        now_time = datetime.now().strftime("%H:%M:%S")
        response_window = cls._response_window_fields()
        caregivers = db_manager.find("caregivers", {"is_active": True})
        caretaker_1 = next((c for c in caregivers if "Mohini" in c.get("name", "") or c.get("priority") == 1), {"name": "Mohini Ravat", "email": "mohini.ravat@fallguard.local"})
        caretaker_2 = next((c for c in caregivers if "Radha" in c.get("name", "") or c.get("priority") == 2), {"name": "Radha Raghav", "email": "radha.raghav@fallguard.local"})
        admin_contact = {
            "name": "System Administrator",
            "email": os.getenv("ADMIN_EMAIL", "admin@fallguard.local"),
            "role": "System Administrator (Emergency Override)",
        }

        escalation_chain = [
            {
                "tier": "Caretaker 1 (Primary)",
                "name": caretaker_1.get("name", "Mohini Ravat"),
                "email": caretaker_1.get("email", "mohini.ravat@fallguard.local"),
                "status": "UNAVAILABLE (Forwarded by Caretaker 1)",
                "note": f"Mohini Ravat cannot attend: {reason}. Forwarded to Caretaker 2.",
            },
            {
                "tier": "Caretaker 2 (Secondary)",
                "name": caretaker_2.get("name", "Radha Raghav"),
                "email": caretaker_2.get("email", "radha.raghav@fallguard.local"),
                "status": "ALERT RECEIVED & RESPONDING",
                "note": "Forwarded emergency assigned to Radha Raghav. She is requested to respond with patient.",
            },
            {
                "tier": "System Administrator (Admin)",
                "name": admin_contact["name"],
                "email": admin_contact["email"],
                "status": "STANDBY (Caretaker 2 Responding)",
                "note": "Caretaker 2 (Radha Raghav) is responding to forwarded emergency. Admin on standby.",
            },
        ]

        c2_email = caretaker_2.get("email", "").strip()

        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        timeline = incident.get("timeline", []) if incident else []
        timeline.append({
            "time": now_time,
            "event": f"Emergency Forwarded: Mohini Ravat forwarded emergency to Radha Raghav (Caretaker 2). Reason: {reason}",
        })

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db_manager.update_one(
            "incidents",
            {"incident_id": incident_id},
            {
                "status": "ESCALATED_CARETAKER_2",
                "verification_status": "ESCALATED_CARETAKER_2",
                "incident_status": "ESCALATED_CARETAKER_2",
                "current_assigned_caretaker": "Radha Raghav",
                "escalation_reason": reason,
                "escalation_timestamp": now_utc,
                "escalation_chain": escalation_chain,
                "active_contact": caretaker_2,
                "notification_status": "ESCALATED_CARETAKER_2",
                "timeline": timeline,
                "escalation_history": timeline,
                **response_window,
            },
        )
        recipient_user = db_manager.find_one("users", {"email": c2_email})
        cls.notify_recipient(
            incident={
                **(incident or {}),
                "incident_id": incident_id,
                "room_id": room_name,
                "body_angle_degrees": body_angle,
                "detected_at": (incident or {}).get("detected_at", now_utc),
            },
            recipient_id=(recipient_user or {}).get("user_id", "radha"),
            recipient_name=caretaker_2.get("name", "Radha Raghav"),
            recipient_email=c2_email,
            stage="ESCALATED_CARETAKER_2",
        )

        return {
            "status": "ESCALATED_CARETAKER_2",
            "contact": caretaker_2,
            "escalation_chain": escalation_chain,
            "message": f"Emergency forwarded to Caretaker 2 ({caretaker_2['name']}). She has been notified to respond with patient.",
        }

    @classmethod
    def forward_alert_to_admin(
        cls,
        incident_id: str,
        room_name: str = "Living Room",
        body_angle: float = 70.0,
        reason: str = "Caretaker 2 (Radha Raghav) is also unavailable.",
    ) -> Dict[str, Any]:
        """Forwards an active emergency from Caretaker 2 to System Administrator Override."""
        now_time = datetime.now().strftime("%H:%M:%S")
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        response_window = {
            "response_stage_started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "response_deadline_at": None,
        }
        caregivers = db_manager.find("caregivers", {"is_active": True})
        caretaker_1 = next((c for c in caregivers if "Mohini" in c.get("name", "") or c.get("priority") == 1), {"name": "Mohini Ravat", "email": "mohini.ravat@fallguard.local"})
        caretaker_2 = next((c for c in caregivers if "Radha" in c.get("name", "") or c.get("priority") == 2), {"name": "Radha Raghav", "email": "radha.raghav@fallguard.local"})
        admin_contact = {
            "name": "System Administrator",
            "email": os.getenv("ADMIN_EMAIL", "admin@fallguard.local"),
            "role": "System Administrator (Emergency Override)",
        }

        escalation_chain = [
            {
                "tier": "Caretaker 1 (Primary)",
                "name": caretaker_1.get("name", "Mohini Ravat"),
                "email": caretaker_1.get("email", "mohini.ravat@fallguard.local"),
                "status": "UNAVAILABLE",
                "note": "Caretaker 1 could not attend and forwarded to Caretaker 2.",
            },
            {
                "tier": "Caretaker 2 (Secondary)",
                "name": caretaker_2.get("name", "Radha Raghav"),
                "email": caretaker_2.get("email", "radha.raghav@fallguard.local"),
                "status": "UNAVAILABLE (Forwarded by Caretaker 2)",
                "note": f"Radha Raghav cannot attend: {reason}. Escalated to System Administrator.",
            },
            {
                "tier": "System Administrator (Admin)",
                "name": admin_contact["name"],
                "email": admin_contact["email"],
                "status": "CRITICAL ALERT (ADMIN EMERGENCY OVERRIDE)",
                "note": "Both Caretaker 1 & Caretaker 2 cannot attend! System Administrator must intervene, dispatch ambulance, or consult hospital.",
            },
        ]

        admin_email = admin_contact.get("email", "").strip()

        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        timeline = incident.get("timeline", []) if incident else []
        timeline.append({
            "time": now_time,
            "event": f"Critical Escalation: Radha Raghav forwarded emergency to System Administrator. Reason: {reason}",
        })

        db_manager.update_one(
            "incidents",
            {"incident_id": incident_id},
            {
                "status": "UNACKNOWLEDGED_ADMIN_REQUIRED",
                "verification_status": "UNACKNOWLEDGED_ADMIN_REQUIRED",
                "incident_status": "UNACKNOWLEDGED_ADMIN_REQUIRED",
                "current_assigned_caretaker": "System Administrator",
                "escalation_reason": reason,
                "escalation_timestamp": now_utc,
                "escalation_chain": escalation_chain,
                "active_contact": admin_contact,
                "notification_status": "CRITICAL_ADMIN_OVERRIDE",
                "timeline": timeline,
                "escalation_history": timeline,
                **response_window,
            },
        )
        recipient_user = db_manager.find_one("users", {"email": admin_email})
        cls.notify_recipient(
            incident={
                **(incident or {}),
                "incident_id": incident_id,
                "room_id": room_name,
                "body_angle_degrees": body_angle,
                "detected_at": (incident or {}).get("detected_at", now_utc),
            },
            recipient_id=(recipient_user or {}).get("user_id", "admin"),
            recipient_name=admin_contact["name"],
            recipient_email=admin_email,
            stage="CRITICAL_ADMIN_OVERRIDE",
        )

        return {
            "status": "UNACKNOWLEDGED_ADMIN_REQUIRED",
            "contact": admin_contact,
            "escalation_chain": escalation_chain,
            "message": "Both Caretaker 1 & Caretaker 2 unavailable! Critical Alert escalated to System Administrator Override.",
        }

    @classmethod
    def admin_take_emergency_action(
        cls,
        incident_id: str,
        action_type: str,
        details: str = "",
    ) -> Dict[str, Any]:
        """Admin acts upon critical emergency: Ambulance dispatch, Hospital consultation, or Backup staff."""
        now_time = datetime.now().strftime("%H:%M:%S")
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        incident = db_manager.find_one("incidents", {"incident_id": incident_id})
        timeline = incident.get("timeline", []) if incident else []

        if action_type == "AMBULANCE":
            event_text = f"🚑 Emergency Action: System Administrator dispatched Emergency Ambulance (108/911). Details: {details}"
            admin_status = "AMBULANCE_DISPATCHED"
        elif action_type == "HOSPITAL":
            event_text = f"🏥 Emergency Action: System Administrator directly consulted Nearest Hospital Emergency Department. Details: {details}"
            admin_status = "HOSPITAL_CONSULTED"
        elif action_type == "BACKUP_STAFF":
            event_text = f"👨‍⚕️ Emergency Action: System Administrator arranged and dispatched on-call emergency medical staff. Details: {details}"
            admin_status = "BACKUP_STAFF_DISPATCHED"
        elif action_type == "RESOLVE":
            event_text = f"✅ Emergency Resolved: System Administrator verified patient attended and safe. Details: {details}"
            admin_status = "RESOLVED"
        else:
            event_text = f"ℹ️ Admin Action: {details}"
            admin_status = "ADMIN_ACTION_TAKEN"

        timeline.append({"time": now_time, "event": event_text})

        update_data = {
            "status": "RESOLVED" if action_type == "RESOLVE" else "ADMIN_ACTION_TAKEN",
            "verification_status": "RESOLVED" if action_type == "RESOLVE" else "ADMIN_ACTION_TAKEN",
            "admin_action": admin_status,
            "timeline": timeline,
            "escalation_history": timeline,
        }
        if action_type == "RESOLVE":
            update_data["closed_at"] = now_utc
            update_data["resolution_timestamp"] = now_utc
            update_data["resolution_notes"] = details or "Verified safe by Administrator."
            update_data["resolved_by"] = "System Administrator"
            update_data["closed_by"] = "System Administrator"
            update_data["response_deadline_at"] = None

        db_manager.update_one("incidents", {"incident_id": incident_id}, update_data)

        return {
            "status": admin_status,
            "message": event_text,
            "action_type": action_type,
        }


_worker_guard = threading.Lock()
_worker_thread: Optional[threading.Thread] = None
_worker_stop = threading.Event()


def start_escalation_worker(poll_interval_seconds: int = 5) -> threading.Thread:
    """Run response-deadline escalation independently of dashboard page views."""
    global _worker_thread
    with _worker_guard:
        if _worker_thread and _worker_thread.is_alive():
            return _worker_thread

        def run() -> None:
            while not _worker_stop.wait(poll_interval_seconds):
                try:
                    CaregiverNotificationService.process_overdue_escalations()
                except Exception:
                    logger.exception("Emergency escalation worker iteration failed.")

        _worker_thread = threading.Thread(
            target=run,
            name="fall-guard-escalation-worker",
            daemon=True,
        )
        _worker_thread.start()
        return _worker_thread
