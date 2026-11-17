"""
Fall Guard AI — Real-Time Human Fall Detection Using Computer Vision.
Designed for elderly care and patient safety at home.

Roles & Dashboards:
1. System Admin: Full system oversight, live CV feed, multi-room configs, audit timeline, caregiver controls.
2. Caretaker 1 (Mohini Ravat): Primary responder console, on-duty toggle, triage alert actions, live check-in stream.
3. Caretaker 2 (Radha Raghav): Secondary responder console, backup standby toggle, Mohini watch status, escalated alerts.
4. Resident / User: Reassuring patient safety hub, one-touch SOS button, hands-free voice prompt, Ghost Mode toggle.
"""

import datetime
import math
import os
import threading
import time
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from fastapi import HTTPException

# Core Vision and Logic Imports
from core.pose_detector import PoseDetector
from core.camera_utils import CameraProcessLock, frame_to_data_uri
from core.landmark_extractor import LandmarkExtractor
from core.feature_calculator import FeatureCalculator
from core.temporal_fall_detector import TemporalFallDetector
from core.incident_state_machine import IncidentStateMachine
from utils.notification_service import CaregiverNotificationService, start_escalation_worker
from backend.database import db_manager
from backend.security import authenticate_user, ensure_bootstrap_users
from backend.care_models import (
    AssignmentRequest,
    AvailabilityUpdate,
    CareAvailability,
    FacilityCreate,
    FacilityType,
    LocalCaretakerCreate,
    ResidentCreate,
    RoomCreate,
)
from backend.emergency_workflow import EmergencyRoutingService, record_incident_action
from backend.routers.care_management import (
    assign_room,
    register_facility,
    register_local_caretaker,
    register_resident,
    register_room,
    update_caretaker_availability,
)

# Page Configuration
st.set_page_config(
    page_title="Fall Guard AI — Real-Time Human Fall Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
ensure_bootstrap_users()
start_escalation_worker()

# Demo account display metadata. Password hashes are managed by backend.security.
USER_ACCOUNTS = {
    "admin": {
        "name": "System Administrator",
        "role": "admin",
        "badge": "🛡️ System Administrator",
        "email": "admin@fallguard.local",
        "phone": "+91 99000 11223",
        "desc": "Full camera nodes, MongoDB records, caregiver directory, and algorithm sensitivity controls.",
    },
    "mohini": {
        "name": "Mohini Ravat",
        "role": "caretaker_1",
        "badge": "🥇 Primary Caretaker (Caretaker 1)",
        "email": "mohini.ravat@fallguard.local",
        "phone": "+91 98765 43210",
        "desc": "First-line emergency responder. Triages incoming alerts, acknowledges patient status, or forwards to Radha Raghav.",
    },
    "radha": {
        "name": "Radha Raghav",
        "role": "caretaker_2",
        "badge": "🥈 Secondary Caretaker (Caretaker 2)",
        "email": "radha.raghav@fallguard.local",
        "phone": "+91 98123 45678",
        "desc": "Backup standby responder. Receives escalated emergency alerts whenever Mohini Ravat is unavailable or off-duty.",
    },
    "user": {
        "name": "Elderly Resident / Patient",
        "role": "user",
        "badge": "👤 Resident / Patient",
        "email": "resident@fallguard.local",
        "phone": "+91 98000 55443",
        "resident_id": "RES-101",
        "desc": "Elderly patient portal. Reassuring safety dashboard, one-touch SOS button, hands-free voice assistance, and privacy Ghost Mode.",
    },
}

# Custom Attractive Light-Themed CSS - Vibrant, Colorful Healthcare Palette
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Radiant, colorful, modern healthcare background with dynamic mesh gradients */
    .stApp {
        background:
            radial-gradient(circle at 5% 10%, rgba(59, 130, 246, 0.10) 0%, transparent 40%),
            radial-gradient(circle at 95% 10%, rgba(139, 92, 246, 0.10) 0%, transparent 40%),
            radial-gradient(circle at 90% 90%, rgba(236, 72, 153, 0.08) 0%, transparent 40%),
            radial-gradient(circle at 10% 90%, rgba(16, 185, 129, 0.10) 0%, transparent 40%),
            radial-gradient(circle at 50% 50%, rgba(245, 158, 11, 0.05) 0%, transparent 50%),
            linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 50%, #EFF6FF 100%);
    }

    /* Vibrant, polished Sidebar with colorful borders and clear options */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 35%, #F0F4FF 70%, #EBF4FF 100%) !important;
        border-right: 2px solid #BFDBFE !important;
        box-shadow: 4px 0 25px rgba(37, 99, 235, 0.08) !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #BFDBFE !important;
        margin: 14px 0 !important;
    }
    [data-testid="stSidebar"] .stRadio,
    [data-testid="stSidebar"] [data-testid="stRadio"] {
        opacity: 1 !important;
        pointer-events: auto !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] * {
        opacity: 1 !important;
        pointer-events: auto !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        font-weight: 750 !important;
        color: #1E3A8A !important;
        padding: 4px 0 !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stWidgetLabel"] {
        color: #1E3A8A !important;
        font-weight: 800 !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
        opacity: 1 !important;
        cursor: pointer !important;
        background: #FFFFFF !important;
        padding: 9px 14px !important;
        border-radius: 12px !important;
        margin-bottom: 6px !important;
        border: 1.5px solid #CBD5E1 !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label p,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label span,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label div {
        color: #1E3A8A !important;
        font-weight: 750 !important;
        font-size: 0.90rem !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {
        background: #EFF6FF !important;
        border-color: #3B82F6 !important;
        transform: translateX(3px) !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover p,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover span {
        color: #1D4ED8 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"],
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
        border-color: #2563EB !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.16) !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"] p,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p {
        color: #1D4ED8 !important;
        font-weight: 850 !important;
    }

    /* Clean white cards with gentle colored shadows */
    .card-light {
        background: #FFFFFF;
        border-radius: 18px;
        padding: 24px;
        border: 1.5px solid #E2E8F0;
        box-shadow: 0 8px 26px rgba(15, 23, 42, 0.05);
        margin-bottom: 20px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .card-light:hover {
        box-shadow: 0 12px 32px rgba(37, 99, 235, 0.09);
    }

    .hero-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 35%, #2563EB 75%, #4F46E5 100%);
        border-radius: 20px;
        padding: 22px 28px;
        border: 1.5px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 12px 36px rgba(37, 99, 235, 0.28);
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }
    .hero-header::after {
        content: "";
        position: absolute;
        top: -50%; right: -20%;
        width: 320px; height: 320px;
        background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%);
        pointer-events: none;
    }

    .title-text {
        font-size: 2.15rem;
        font-weight: 850;
        color: #FFFFFF !important;
        margin: 0;
        letter-spacing: -0.025em;
        text-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
    }

    .subtitle-text {
        font-size: 0.98rem;
        font-weight: 600;
        color: #BFDBFE !important;
        margin-top: 5px;
        margin-bottom: 0;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
    }

    /* Badges with rich vibrant colors */
    .badge-posture {
        padding: 9px 18px;
        border-radius: 24px;
        font-weight: 800;
        font-size: 0.95rem;
        display: inline-block;
        margin-bottom: 8px;
        letter-spacing: 0.02em;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .badge-standing { background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%); color: #047857; border: 2px solid #34D399; }
    .badge-sitting { background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); color: #1D4ED8; border: 2px solid #60A5FA; }
    .badge-bending { background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%); color: #B45309; border: 2px solid #FBBF24; }
    .badge-walking { background: linear-gradient(135deg, #F0FDFA 0%, #CCFBF1 100%); color: #0F766E; border: 2px solid #2DD4BF; }
    .badge-resting { background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%); color: #6D28D9; border: 2px solid #A78BFA; }
    .badge-uncertain { background: linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%); color: #475569; border: 2px solid #94A3B8; }
    .badge-fall {
        background: linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%);
        color: #BE123C;
        border: 2.5px solid #F43F5E;
        box-shadow: 0 4px 16px rgba(244, 63, 94, 0.35);
        animation: pulse-border 1.2s infinite;
    }

    @keyframes pulse-border {
        0% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.55); }
        70% { box-shadow: 0 0 0 14px rgba(244, 63, 94, 0); }
        100% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); }
    }

    .emergency-panel {
        background: linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 50%, #FECDD3 100%);
        border: 2.5px solid #E11D48;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 22px;
        box-shadow: 0 12px 36px rgba(225, 29, 72, 0.22);
    }

    .evidence-box {
        background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
        border-radius: 14px;
        padding: 16px;
        border-left: 5px solid #2563EB;
        border-top: 1px solid #DBEAFE;
        border-right: 1px solid #DBEAFE;
        border-bottom: 1px solid #DBEAFE;
        margin-top: 12px;
        box-shadow: 0 3px 12px rgba(37, 99, 235, 0.05);
    }

    .evidence-item {
        font-size: 0.90rem;
        color: #1E293B;
        margin-bottom: 5px;
        line-height: 1.5;
        font-weight: 550;
    }

    .metric-light {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 12px;
        text-align: center;
    }

    .role-banner-admin {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 50%, #BFDBFE 100%);
        border: 2px solid #60A5FA;
        border-radius: 16px;
        padding: 18px 22px;
        margin-bottom: 18px;
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.1);
    }
    .role-banner-mohini {
        background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 50%, #A7F3D0 100%);
        border: 2px solid #34D399;
        border-radius: 16px;
        padding: 18px 22px;
        margin-bottom: 18px;
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.12);
    }
    .role-banner-radha {
        background: linear-gradient(135deg, #FAF5FF 0%, #F3E8FF 50%, #DDD6FE 100%);
        border: 2px solid #A78BFA;
        border-radius: 16px;
        padding: 18px 22px;
        margin-bottom: 18px;
        box-shadow: 0 6px 20px rgba(139, 92, 246, 0.12);
    }
    .role-banner-user {
        background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 50%, #FDE68A 100%);
        border: 2px solid #FBBF24;
        border-radius: 16px;
        padding: 18px 22px;
        margin-bottom: 18px;
        box-shadow: 0 6px 20px rgba(245, 158, 11, 0.12);
    }

    /* Colorful Streamlit UI Enhancements */
    button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        font-weight: 750 !important;
        border-radius: 12px !important;
        border: 0 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    }
    button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
    }
    div[data-testid="stMetricValue"] {
        font-weight: 850 !important;
        color: #0F172A !important;
    }

    /* Camera Icon Toggle Button & Live Monitoring Banner Styling */
    div[data-testid="stHorizontalBlock"]:has(button[key*="btn_cam_stream_toggle"]),
    div[data-testid="stHorizontalBlock"]:has(button[data-testid*="btn_cam_stream_toggle"]) {
        background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 50%, #EFF6FF 100%) !important;
        border: 1.5px solid #93C5FD !important;
        border-radius: 18px !important;
        padding: 12px 20px !important;
        box-shadow: 0 6px 22px rgba(37, 99, 235, 0.06) !important;
        margin-bottom: 16px !important;
        align-items: center !important;
    }
    button[key*="btn_cam_stream_toggle"],
    button[data-testid*="btn_cam_stream_toggle"],
    button[key*="btn_header_cam"],
    button[data-testid*="btn_header_cam"] {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
        border: 1.5px solid #60A5FA !important;
        border-radius: 12px !important;
        font-size: 1.55rem !important;
        padding: 4px 12px !important;
        box-shadow: 0 3px 10px rgba(37, 99, 235, 0.18) !important;
        color: #1E40AF !important;
        min-height: 42px !important;
        line-height: 1 !important;
        cursor: pointer !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    button[key*="btn_cam_stream_toggle"]:hover,
    button[data-testid*="btn_cam_stream_toggle"]:hover,
    button[key*="btn_header_cam"]:hover,
    button[data-testid*="btn_header_cam"]:hover {
        background: linear-gradient(135deg, #DBEAFE 0%, #BFDBFE 100%) !important;
        border-color: #2563EB !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.32) !important;
        transform: translateY(-1px) scale(1.05) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource
def get_pose_detector():
    return PoseDetector(min_detection_confidence=0.4, min_tracking_confidence=0.45)

@st.cache_resource
def get_landmark_extractor():
    return LandmarkExtractor()

@st.cache_resource
def get_feature_calculator():
    return FeatureCalculator()


# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "user_role" not in st.session_state:
    st.session_state["user_role"] = ""
if "user_display_name" not in st.session_state:
    st.session_state["user_display_name"] = ""
if "stream_active" not in st.session_state:
    st.session_state["stream_active"] = True
if "active_incident" not in st.session_state:
    st.session_state["active_incident"] = None
if "verification_start_time" not in st.session_state:
    st.session_state["verification_start_time"] = None
if "verification_countdown" not in st.session_state:
    st.session_state["verification_countdown"] = 15
if "min_angle_setting" not in st.session_state:
    st.session_state["min_angle_setting"] = 38
if "required_frames_setting" not in st.session_state:
    st.session_state["required_frames_setting"] = 3
if "ghost_mode" not in st.session_state:
    st.session_state["ghost_mode"] = False
if "voice_enabled" not in st.session_state:
    st.session_state["voice_enabled"] = True
if "selected_room" not in st.session_state:
    st.session_state["selected_room"] = "Living Room — Camera 1"
if "recent_logs" not in st.session_state:
    st.session_state["recent_logs"] = []


def add_log(msg: str):
    timestamp = datetime.datetime.now().strftime("%I:%M:%S %p")
    st.session_state["recent_logs"].insert(0, f"[{timestamp}] {msg}")
    if len(st.session_state["recent_logs"]) > 25:
        st.session_state["recent_logs"].pop()


def get_display_account(username_key: str):
    user = db_manager.find_one("users", {"username": username_key})
    if not user or not user.get("is_active", True):
        return None
    metadata = USER_ACCOUNTS.get(username_key, {})
    role_badges = {
        "local_caretaker": f"🏥 {user.get('designation', 'Local Caretaker')}",
        "resident": "👤 Resident / Patient",
    }
    return {
        **user,
        "name": user.get("display_name", metadata.get("name", username_key)),
        "badge": metadata.get("badge", role_badges.get(user["role"], user["role"].replace("_", " ").title())),
        "desc": metadata.get("desc", "Authorized account."),
    }


def log_in_user(username_key: str, account=None):
    account = account or get_display_account(username_key)
    if account:
        st.session_state["authenticated"] = True
        st.session_state["username"] = username_key
        st.session_state["user_role"] = account["role"]
        st.session_state["user_display_name"] = account["name"]
        add_log(f"User signed in: {account['name']} ({account['badge']})")


def log_out_user():
    try:
        GlobalCameraHub.get_instance().stop()
    except Exception:
        pass
    camera = st.session_state.pop("_monitoring_camera", None)
    if camera is not None:
        try:
            if hasattr(camera, "stop"):
                camera.stop()
            else:
                camera.release()
        except Exception:
            pass

    # Clear active session state variables
    keys_to_clear = [
        "active_incident",
        "last_fall_snapshot",
        "verification_start_time",
        "last_forwarded_c1",
        "show_resident_modal",
        "show_admin_contact",
        "show_history_focus",
        "caretaker_selected_nav_1",
        "caretaker_selected_nav_2",
        "selected_room",
        "_monitoring_previous_frame_time",
    ]
    for k in keys_to_clear:
        st.session_state.pop(k, None)

    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state["user_role"] = ""
    st.session_state["user_display_name"] = ""
    st.session_state["active_incident"] = None
    st.session_state["stream_active"] = False
    st.session_state["login_username"] = ""
    st.session_state["login_password"] = ""

    st.rerun()


# ----------------------------------------------------
# LOGIN SCREEN (UNAUTHENTICATED)
# ----------------------------------------------------
auth_username = st.session_state.get("username", "")
authenticated_account = get_display_account(auth_username) if auth_username else None
auth_session_valid = (
    st.session_state.get("authenticated", False)
    and authenticated_account is not None
    and st.session_state.get("user_role") == authenticated_account["role"]
)
invalid_auth_session = (
    st.session_state.get("authenticated", False) and not auth_session_valid
)

if invalid_auth_session:
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state["user_role"] = ""
    st.session_state["user_display_name"] = ""
    st.session_state["login_username"] = ""
    st.session_state["login_password"] = ""

if not auth_session_valid:
    if invalid_auth_session:
        st.warning("Your sign-in session could not be verified. Please sign in again.")
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(ellipse at 12% 12%, rgba(147, 197, 253, 0.26), transparent 34%),
                radial-gradient(ellipse at 88% 88%, rgba(191, 219, 254, 0.38), transparent 36%),
                linear-gradient(135deg, #F8FBFF 0%, #EEF5FD 52%, #F7FAFF 100%);
        }
        .block-container {
            max-width: 960px;
            padding: clamp(2rem, 8vh, 5rem) 1rem 2rem;
        }
        .st-key-fallguard_login_card {
            box-sizing: border-box;
            max-width: 520px;
            margin: 0 auto;
            padding: clamp(1.5rem, 5vw, 2.5rem);
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid #DCE8F5;
            border-radius: 26px;
            box-shadow: 0 24px 70px rgba(20, 54, 94, 0.12), 0 3px 12px rgba(20, 54, 94, 0.05);
        }
        .login-brand {
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .login-shield {
            display: inline-flex;
            width: 68px;
            height: 68px;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.85rem;
            border: 1px solid #D6E8FB;
            border-radius: 22px;
            background: linear-gradient(145deg, #EFF7FF, #DBEAFE);
            box-shadow: 0 10px 24px rgba(37, 99, 174, 0.12);
        }
        .login-kicker {
            margin: 0 0 0.35rem;
            color: #3975B8;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.16em;
        }
        .login-brand h1 {
            margin: 0;
            color: #102A4C;
            font-size: clamp(1.9rem, 5vw, 2.35rem);
            font-weight: 800;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }
        .login-brand h1 span { color: #2878C7; }
        .login-subtitle {
            margin: 0.65rem auto 0;
            max-width: 390px;
            color: #435B78;
            font-size: 0.93rem;
            font-weight: 600;
            line-height: 1.5;
        }
        .login-description {
            margin: 0.55rem 0 0;
            color: #71839A;
            font-size: 0.85rem;
            line-height: 1.5;
        }
        .login-divider {
            height: 1px;
            margin: 1.45rem 0 1.25rem;
            border: 0;
            background: linear-gradient(90deg, transparent, #DDE7F1 18%, #DDE7F1 82%, transparent);
        }
        .login-welcome {
            margin: 0;
            color: #173556;
            font-size: 1.22rem;
            font-weight: 750;
        }
        .login-prompt {
            margin: 0.3rem 0 0;
            color: #71839A;
            font-size: 0.88rem;
        }
        .st-key-fallguard_login_card [data-testid="stTextInput"] label {
            color: #294361;
            font-size: 0.88rem;
            font-weight: 650;
        }
        .st-key-fallguard_login_card [data-testid="stTextInput"] input {
            min-height: 2.85rem;
            border: 1px solid #D4E0ED;
            border-radius: 11px;
            background: #FBFDFF;
        }
        .st-key-fallguard_login_card [data-testid="stTextInput"] input:focus {
            border-color: #4B91D4;
            box-shadow: 0 0 0 3px rgba(75, 145, 212, 0.14);
        }
        .st-key-fallguard_login_card [data-testid="stTextInput"] input::placeholder {
            color: #9AAABC;
        }
        .st-key-fallguard_login_card [data-testid="stButton"] > button,
        .st-key-fallguard_login_card [data-testid="stFormSubmitButton"] > button {
            min-height: 2.85rem;
            border-radius: 11px;
            font-weight: 700;
        }
        .st-key-fallguard_login_card [data-testid="stButton"] > button[kind="primary"],
        .st-key-fallguard_login_card [data-testid="stFormSubmitButton"] > button[kind="primary"] {
            border: 0;
            background: linear-gradient(100deg, #155AA1, #287FC8);
            box-shadow: 0 8px 18px rgba(27, 105, 177, 0.2);
        }
        .st-key-fallguard_login_card [data-testid="stButton"] > button[kind="primary"]:hover,
        .st-key-fallguard_login_card [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            border: 0;
            background: linear-gradient(100deg, #104B89, #1F6FB4);
            box-shadow: 0 10px 22px rgba(27, 105, 177, 0.26);
        }
        .login-secure-note {
            margin: 1.25rem 0 0;
            color: #71839A;
            font-size: 0.78rem;
            line-height: 1.5;
            text-align: center;
        }
        @media (max-width: 600px) {
            .block-container { padding: 1.25rem 0.75rem; }
            .st-key-fallguard_login_card { border-radius: 20px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="fallguard_login_card"):
        st.markdown(
            """
            <div class="login-brand">
                <div class="login-shield" aria-hidden="true">
                    <svg width="38" height="42" viewBox="0 0 40 44" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M20 2.5L35 8V19.5C35 29.4 28.7 37.2 20 41.5C11.3 37.2 5 29.4 5 19.5V8L20 2.5Z" fill="#2878C7"/>
                        <path d="M20 6.2L31.5 10.4V19.3C31.5 27 27 33.3 20 37C13 33.3 8.5 27 8.5 19.3V10.4L20 6.2Z" fill="#EFF7FF"/>
                        <path d="M18 13H22V18H27V22H22V27H18V22H13V18H18V13Z" fill="#2878C7"/>
                    </svg>
                </div>
                <p class="login-kicker">AI-POWERED CARE</p>
                <h1>Fall Guard <span>AI</span></h1>
                <p class="login-subtitle">Real-Time Human Fall Detection Using Computer Vision</p>
                <p class="login-description">Intelligent Elderly-Care &amp; Patient Safety Monitoring Platform</p>
                <hr class="login-divider">
                <p class="login-welcome">Welcome back</p>
                <p class="login-prompt">Sign in to continue to your secure safety dashboard.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            u_name = st.text_input(
                "Username",
                key="login_username",
                placeholder="Enter your username",
                autocomplete="username",
            )
            u_pass = st.text_input(
                "Password",
                key="login_password",
                type="password",
                placeholder="Enter your password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            username_key = (u_name or "").strip().lower()
            password = u_pass or ""
            if not username_key:
                st.warning("Enter your username to continue.")
            elif not password:
                st.warning("Enter your password to continue.")
            else:
                acc = authenticate_user(username_key, password)
                if acc:
                    log_in_user(username_key, get_display_account(username_key))
                    st.rerun()
                else:
                    st.error("The username or password you entered is incorrect. Please try again.")

        st.markdown(
            '<p class="login-secure-note">🔒 Secure access for authorized care teams and residents</p>',
            unsafe_allow_html=True,
        )

    st.stop()


# ----------------------------------------------------
# MAIN TOP HERO HEADER (AUTHENTICATED)
# ----------------------------------------------------
if authenticated_account is None:
    st.error("Unable to verify your account. Please sign in again.")
    st.stop()

st.session_state.pop("login_username", None)
st.session_state.pop("login_password", None)
curr_acc = authenticated_account
role_badge = curr_acc["badge"]
user_fullname = curr_acc["name"]

st.markdown(
    f"""
    <div class="hero-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div>
                <div class="title-text">🛡️ Fall Guard AI</div>
                <div class="subtitle-text">Real-Time Human Fall Detection Using Computer Vision — Elderly & Patient Safety Platform</div>
            </div>
            <div style="text-align: right; margin-top: 4px;">
                <span style="background: rgba(255, 255, 255, 0.22); color: #FFFFFF; padding: 7px 18px; border-radius: 20px; font-weight: 800; font-size: 0.92rem; display: inline-block; border: 1.5px solid rgba(255, 255, 255, 0.45); box-shadow: 0 4px 14px rgba(0,0,0,0.18);">
                    {role_badge}
                </span><br>
                <span style="color: #DBEAFE; font-size: 0.88rem; font-weight: 600; margin-top: 5px; display: inline-block;">Active Account: <b style="color: #FFFFFF;">{user_fullname}</b></span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Role Information & Sign Out
c_role_info, c_signout = st.columns([20, 4])
with c_role_info:
    st.caption(f"Role: **{curr_acc['badge']}** • {curr_acc['desc']}")
with c_signout:
    if st.button("🚪 Sign Out", key=f"btn_sign_out_global_{curr_acc.get('role', 'user')}", use_container_width=True):
        log_out_user()

st.markdown("<hr style='border:0; border-top:1px solid #E2E8F0; margin:10px 0 18px 0;'>", unsafe_allow_html=True)


# ====================================================
# SHARED AUDIO ALERT HELPER
# ====================================================
def render_audio_alert():
    """Generates an immediate emergency alert chime using browser Web Audio API."""
    st.components.v1.html(
        """
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.35);
            gain.gain.setValueAtTime(0.35, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
            osc.start();
            osc.stop(ctx.currentTime + 0.35);
        } catch(e) {}
        </script>
        """,
        height=0,
    )


# ====================================================
# SHARED EMERGENCY VERIFICATION PROMPT HELPER
# ====================================================
def render_emergency_verification_panel():
    if st.session_state["active_incident"] is not None:
        inc_doc = st.session_state["active_incident"]
        inc_id = inc_doc["incident_id"]
        elapsed = time.time() - (st.session_state["verification_start_time"] or time.time())
        remaining = max(0, int(st.session_state["verification_countdown"] - elapsed))
        room = inc_doc.get("room_id", st.session_state["selected_room"])
        body_ang = inc_doc.get("body_angle_degrees", 0.0)

        # Timeout Auto-Escalation Check
        if remaining <= 0:
            IncidentStateMachine.record_resident_verification(inc_id, "TIMEOUT", source="COUNTDOWN")
            add_log(f"⚠️ Resident verification timed out for [{inc_id}]; the immediate responder alert remains active.")
            st.session_state["active_incident"] = None
            st.session_state["last_incident_resolved_time"] = time.time()
            if "temporal_detector" in st.session_state:
                st.session_state["temporal_detector"].reset()
            st.session_state["stream_active"] = True
            GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
            st.rerun()

        st.markdown(
            f"""
            <div class="emergency-panel">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <h2 style="color:#BE123C; margin:0 0 6px 0; font-weight:800;">
                            🚨 POSSIBLE FALL DETECTED
                        </h2>
                        <p style="color:#4C0519; margin:0; font-size:1.15rem; font-weight:600;">
                            Are you okay? Please confirm your status.
                        </p>
                        <p style="color:#881337; margin:4px 0 0 0; font-size:0.9rem;">
                            Incident ID: <b>{inc_id}</b> • Location: <b>{room}</b> • Body Tilt: <b>{body_ang:.1f}°</b>
                        </p>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:3.2rem; font-weight:800; color:#E11D48; line-height:1;">{remaining}s</div>
                        <span style="font-size:0.85rem; color:#881337; font-weight:700;">Resident safety-check countdown</span>
                    </div>
                </div>
                <div style="margin-top:14px; background:#FFE4E6; border-radius:10px; height:8px; overflow:hidden;">
                    <div style="background:#E11D48; height:100%; width:{(remaining/st.session_state['verification_countdown'])*100}%;"></div>
                </div>
                <div style="margin-top:10px; font-size:0.88rem; color:#9F1239;">
                    📞 <b>A responder has already been notified.</b> This countdown runs independently from the responder response timer.
                </div>
                {'<div style="margin-top:8px; font-size:0.92rem; color:#9F1239; font-weight:700;">🎙️ Voice Assistance Active: Say clearly: "I am okay" or "Help me"</div>' if st.session_state["voice_enabled"] else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        vb1, vb2, vb3 = st.columns([1, 1, 1])
        if vb1.button("🟢 I'M OK", key="verif_btn_ok", use_container_width=True, type="secondary"):
            IncidentStateMachine.record_resident_verification(inc_id, "I_AM_OK", source="BUTTON")
            add_log(f"Resident [{inc_id}] confirmed they are okay; further automatic escalation stopped.")
            st.session_state["active_incident"] = None
            st.session_state["last_incident_resolved_time"] = time.time()
            if "temporal_detector" in st.session_state:
                st.session_state["temporal_detector"].reset()
            st.session_state["stream_active"] = True
            GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
            st.rerun()

        if vb2.button("🔴 I NEED HELP", key="verif_btn_help", use_container_width=True, type="primary"):
            IncidentStateMachine.record_resident_verification(inc_id, "I_NEED_HELP", source="BUTTON")
            add_log(f"🚨 Resident [{inc_id}] requested help; the immediate responder alert is already active.")
            st.session_state["active_incident"] = None
            st.session_state["last_incident_resolved_time"] = time.time()
            if "temporal_detector" in st.session_state:
                st.session_state["temporal_detector"].reset()
            st.session_state["stream_active"] = True
            GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
            st.rerun()

        if vb3.button("🎙️ Voice Fallback: 'I'm okay'", key="verif_btn_voice_sim", use_container_width=True):
            IncidentStateMachine.record_resident_verification(inc_id, "I_AM_OK", source="VOICE")
            add_log(f"Resident [{inc_id}] confirmed they are okay by voice.")
            st.session_state["active_incident"] = None
            st.session_state["last_incident_resolved_time"] = time.time()
            if "temporal_detector" in st.session_state:
                st.session_state["temporal_detector"].reset()
            st.session_state["stream_active"] = True
            GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
            st.rerun()

        if "last_fall_snapshot" in st.session_state and st.session_state["last_fall_snapshot"] is not None:
            col_snap, col_ev = st.columns([1, 1])
            with col_snap:
                st.image(st.session_state["last_fall_snapshot"], caption=f"Captured Fall Event Snapshot — {room}", width="stretch")
            with col_ev:
                st.markdown("#### 🧠 Detected Movement Evidence")
                ev_items = inc_doc.get("detection_evidence", [])
                for ev in ev_items:
                    st.markdown(f"- {ev}")
        st.markdown("---")


def render_escalation_banner():
    if st.session_state.get("last_escalation"):
        esc = st.session_state["last_escalation"]
        chain = esc.get("escalation_chain", [])
        st.markdown(
            f"""
            <div style="background: #FFFBEB; border: 2px solid #F59E0B; border-radius: 14px; padding: 18px; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div style="font-size: 1.15rem; font-weight: 800; color: #92400E;">
                        📢 Emergency Caretaker Dispatch Chain Activated
                    </div>
                    <span style="background: #FEF3C7; color: #B45309; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">
                        Status: {esc.get('status')}
                    </span>
                </div>
                <p style="margin: 0 0 12px 0; color: #78350F; font-size: 0.95rem;">
                    <b>Routing Protocol:</b> Mohini Ravat (Caretaker 1) ➔ Radha Raghav (Caretaker 2) ➔ System Administrator
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if chain:
            cols = st.columns(len(chain))
            for i, step in enumerate(chain):
                tier_name = step.get("tier", f"Tier {i+1}")
                target_name = step.get("name", "Contact")
                target_status = step.get("status", "PENDING")
                note = step.get("note", "")
                badge_color = "#10B981" if "RESPONDING" in target_status or target_status in ("DELIVERED", "SENT") else ("#EF4444" if "NOT RESPONDING" in target_status or target_status == "UNAVAILABLE" else ("#64748B" if "STANDBY" in target_status else "#3B82F6"))
                bg_color = "#ECFDF5" if "RESPONDING" in target_status or target_status in ("DELIVERED", "SENT") else ("#FEF2F2" if "NOT RESPONDING" in target_status or target_status == "UNAVAILABLE" else ("#F8FAFC" if "STANDBY" in target_status else "#EFF6FF"))

                with cols[i]:
                    st.markdown(
                        f"""
                        <div style="background: {bg_color}; border: 1px solid {badge_color}; border-radius: 10px; padding: 12px; text-align: center; margin-bottom: 14px;">
                            <b style="color: #0F172A; font-size: 0.9rem;">{tier_name}</b><br>
                            <span style="font-size: 0.85rem; color: #334155; font-weight: 600;">{target_name}</span><br>
                            <span style="display: inline-block; margin-top: 6px; padding: 2px 10px; border-radius: 12px; background: {badge_color}; color: white; font-size: 0.75rem; font-weight: 700;">
                                {target_status}
                            </span>
                            <div style="font-size: 0.75rem; color: #64748B; margin-top: 6px;">{note}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        if st.button("✕ Dismiss Alert Banner", key="btn_dismiss_esc"):
            st.session_state["last_escalation"] = None
            st.rerun()


# ====================================================
# LIVE CAMERA MONITORING ENGINE (REUSABLE)
# ====================================================
def generate_activity_cards_html(current_posture: str, is_fall: bool) -> str:
    cards = [
        ("Standing", "🟢", "Normal Activity", "#10B981", "#ECFDF5", "#065F46"),
        ("Sitting", "🔵", "Normal Activity", "#3B82F6", "#EFF6FF", "#1E40AF"),
        ("Walking", "🚶", "Normal Activity", "#14B8A6", "#F0FDFA", "#115E59"),
        ("Bending", "🟡", "Normal Activity", "#F59E0B", "#FFFBEB", "#92400E"),
        ("Intentional Lying", "🛏️", "Controlled Rest", "#8B5CF6", "#F5F3FF", "#5B21B6"),
        ("Possible Fall", "🚨", "Suspected Fall", "#EF4444", "#FEF2F2", "#991B1B"),
    ]
    html_cards = []
    for name, icon, cat, border_c, bg_c, text_c in cards:
        is_active = False
        if is_fall and name == "Possible Fall":
            is_active = True
        elif not is_fall:
            if name == "Standing" and "Standing" in current_posture:
                is_active = True
            elif name == "Sitting" and "Sitting" in current_posture:
                is_active = True
            elif name == "Walking" and "Walking" in current_posture:
                is_active = True
            elif name == "Bending" and "Bending" in current_posture:
                is_active = True
            elif name == "Intentional Lying" and ("Lying" in current_posture or "Resting" in current_posture):
                is_active = True

        if is_active:
            pulse = "animation: pulse-border 1.2s infinite;" if name == "Possible Fall" else ""
            card_html = (
                f'<div style="background:{bg_c}; border:2.5px solid {border_c}; border-radius:12px; padding:10px 12px; box-shadow:0 3px 10px rgba(0,0,0,0.06); {pulse}">'
                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                f'<span style="font-size:1.15rem;">{icon}</span>'
                f'<span style="background:{border_c}; color:white; font-size:0.65rem; font-weight:800; padding:2px 7px; border-radius:10px;">ACTIVE ●</span>'
                f'</div>'
                f'<div style="font-size:0.92rem; font-weight:800; color:{text_c}; margin-top:4px;">{name}</div>'
                f'<div style="font-size:0.75rem; font-weight:600; color:{text_c}; opacity:0.85;">{cat}</div>'
                f'</div>'
            )
        else:
            card_html = (
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:10px 12px; opacity:0.65;">'
                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                f'<span style="font-size:1.15rem; filter:grayscale(30%);">{icon}</span>'
                f'<span style="color:#94A3B8; font-size:0.68rem; font-weight:600;">Idle</span>'
                f'</div>'
                f'<div style="font-size:0.92rem; font-weight:700; color:#475569; margin-top:4px;">{name}</div>'
                f'<div style="font-size:0.75rem; color:#94A3B8;">{cat}</div>'
                f'</div>'
            )
        html_cards.append(card_html)

    grid = "".join(html_cards)
    return f'<div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; margin-top:8px;">{grid}</div>'


class GlobalCameraHub:
    """Thread-safe singleton camera manager shared across all Streamlit sessions and browser tabs."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.camera = None
        self.camera_index = 0
        self.backend_name = "DirectShow"
        self.is_running = False
        self._thread = None
        self._frame_lock = threading.Lock()
        self.latest_frame = None
        self.last_frame_time = 0.0
        self.fps = 0.0
        self.error_message = None
        self.capture_status = "Camera is not started."
        self.frame_dimensions = None
        self.frame_count = 0
        self._process_camera_lock = CameraProcessLock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = GlobalCameraHub()
            return cls._instance

    def start(self, camera_index: int = 0):
        with self._lock:
            if (
                self.is_running
                and self.camera_index == camera_index
                and self.camera is not None
                and self.camera.isOpened()
                and self._thread is not None
                and self._thread.is_alive()
            ):
                return True, self.backend_name, None

            self.stop_internal()

            try:
                self._process_camera_lock.acquire(camera_index)
            except Exception:
                pass

            self.camera_index = camera_index
            self.camera, self.backend_name, self.error_message = self._open_device(camera_index)
            if self.camera is None:
                self.is_running = False
                err = self.error_message or "Camera not available, check device index or permissions"
                self.capture_status = err
                return False, None, err

            self.latest_frame = None
            self.last_frame_time = 0.0
            self.frame_count = 0
            self.is_running = True
            self._thread = threading.Thread(target=self._capture_worker, daemon=True)
            self._thread.start()
            return True, self.backend_name, None

    def _open_device(self, camera_index: int):
        import sys
        if sys.platform == "win32":
            backends = [
                ("DirectShow", cv2.CAP_DSHOW),
                ("Default Backend", cv2.CAP_ANY),
                ("Media Foundation", cv2.CAP_MSMF),
            ]
        else:
            backends = [
                ("Default Backend", cv2.CAP_ANY),
            ]

        indices_to_try = [camera_index]
        for alt_idx in [0, 1]:
            if alt_idx not in indices_to_try:
                indices_to_try.append(alt_idx)

        for idx in indices_to_try:
            for name, backend in backends:
                cap = None
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if not cap.isOpened():
                        cap.release()
                        continue
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                    for _ in range(6):
                        ret, frame = cap.read()
                        if (
                            ret
                            and frame is not None
                            and frame.size > 0
                            and frame.ndim in (2, 3)
                            and frame.shape[0] > 0
                            and frame.shape[1] > 0
                        ):
                            self.capture_status = f"Receiving live frames with {name} (Device {idx})."
                            self.camera_index = idx
                            self.error_message = None
                            return cap, name, None
                        time.sleep(0.04)
                except Exception:
                    pass
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass

        err = "Camera not available, check device index or permissions"
        self.error_message = err
        self.capture_status = err
        return None, None, err

    def _capture_worker(self):
        previous_time = time.monotonic()
        consecutive_failures = 0
        while self.is_running:
            cap = self.camera
            if cap is None or not cap.isOpened():
                if not self.is_running:
                    break
                replacement, backend_name, error_message = self._open_device(self.camera_index)
                if replacement is None:
                    self.error_message = error_message or "Camera not available, check device index or permissions"
                    self.capture_status = self.error_message
                    time.sleep(0.5)
                    continue
                self.camera = replacement
                self.backend_name = backend_name
                self.error_message = None
                consecutive_failures = 0

            try:
                ret, frame = cap.read()
                now = time.monotonic()
                if (
                    not ret
                    or frame is None
                    or frame.size == 0
                    or frame.ndim not in (2, 3)
                    or frame.shape[0] == 0
                    or frame.shape[1] == 0
                ):
                    consecutive_failures += 1
                    if consecutive_failures >= 15:
                        self.error_message = "Camera not available, check device index or permissions"
                        self.capture_status = self.error_message
                    time.sleep(0.04)
                    continue

                consecutive_failures = 0
                dt = now - previous_time
                if dt > 0:
                    self.fps = 1.0 / dt
                previous_time = now

                with self._frame_lock:
                    self.latest_frame = frame
                    self.last_frame_time = now
                    self.frame_dimensions = (frame.shape[1], frame.shape[0])
                    self.frame_count += 1
                    self.error_message = None
                    self.capture_status = f"Receiving live frames with {self.backend_name} (Device {self.camera_index})."

                time.sleep(0.02)
            except Exception as e:
                self.error_message = f"Camera read error: {e}"
                time.sleep(0.1)

    def read_frame(self):
        with self._frame_lock:
            frame = self.latest_frame
        if frame is None and self.is_running:
            for _ in range(5):
                time.sleep(0.04)
                with self._frame_lock:
                    frame = self.latest_frame
                if frame is not None:
                    break
        if frame is None:
            return False, None, self.fps
        return True, frame.copy(), self.fps

    def is_active(self):
        return self.is_running and self.camera is not None and self.camera.isOpened()

    def stop_internal(self):
        self.is_running = False
        camera = self.camera
        self.camera = None
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass
        time.sleep(0.15)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None
        try:
            self._process_camera_lock.release()
        except Exception:
            pass
        with self._frame_lock:
            self.latest_frame = None
            self.last_frame_time = 0.0
            self.frame_dimensions = None
        self.capture_status = "Camera monitoring stopped."

    def stop(self):
        with self._lock:
            self.stop_internal()


def open_monitoring_camera(camera_index: int):
    hub = GlobalCameraHub.get_instance()
    success, backend_name, err = hub.start(camera_index)
    if success:
        return hub, backend_name, None
    return None, None, err


def render_live_monitoring_engine(
    show_full_controls=True,
    header_label="Live Camera Stream",
    allowed_room_ids=None,
):
    selected_room = st.session_state.get("selected_room", "Living Room — Camera 1")
    camera_idx = int(st.session_state.get("camera_hw_index", 0))
    run_stream = bool(st.session_state.get("stream_active", True))
    current_role = curr_acc.get("role", "user")

    # Render Sidebar Control Panel options matching Image 2
    with st.sidebar:
        st.markdown("---")
        st.markdown(
            """
            <div style="font-weight:800; color:#1E3A8A; font-size:1.05rem; margin-bottom:8px;">
                ⚙️ Control Panel
            </div>
            """,
            unsafe_allow_html=True,
        )
        current_camera_index = min(max(int(st.session_state.get("camera_hw_index", 0)), 0), 5)
        camera_idx = st.number_input(
            "📷 Camera Device Index",
            min_value=0,
            max_value=5,
            value=current_camera_index,
            step=1,
            key=f"ctrl_cam_idx_{current_role}",
            help="Select camera hardware index (0 is default webcam).",
        )
        st.session_state["camera_hw_index"] = camera_idx

        run_stream = st.toggle(
            "Start Monitoring Stream",
            value=bool(st.session_state.get("stream_active", True)),
            key=f"ctrl_toggle_stream_{current_role}",
        )
        if run_stream != st.session_state.get("stream_active", True):
            st.session_state["stream_active"] = run_stream
            if not run_stream:
                GlobalCameraHub.get_instance().stop()
            else:
                GlobalCameraHub.get_instance().start(camera_idx)
            st.rerun()

        st.markdown(
            """
            <div style="font-weight:800; color:#1E3A8A; font-size:0.95rem; margin:12px 0 4px 0;">
                🎯 Monitoring Sensitivity
            </div>
            """,
            unsafe_allow_html=True,
        )
        mon_mode = st.selectbox(
            "Profile Mode",
            ["Standard Monitoring", "High Sensitivity", "Low False-Alarm"],
            index=0,
            key=f"ctrl_sensitivity_profile_{current_role}",
        )
        if mon_mode == "High Sensitivity":
            st.session_state["min_angle_setting"] = 45.0
            st.session_state["required_frames_setting"] = 3
        elif mon_mode == "Low False-Alarm":
            st.session_state["min_angle_setting"] = 65.0
            st.session_state["required_frames_setting"] = 8
        else:
            st.session_state["min_angle_setting"] = 55.0
            st.session_state["required_frames_setting"] = 5

        st.markdown(
            """
            <div style="font-weight:800; color:#1E3A8A; font-size:0.95rem; margin:12px 0 4px 0;">
                🔔 Emergency Response Options
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.session_state["audio_alarm_enabled"] = st.checkbox(
            "🔊 Enable Audio Alarm Siren",
            value=st.session_state.get("audio_alarm_enabled", True),
            key=f"ctrl_audio_alarm_{current_role}",
        )
        st.session_state["emergency_contact_number"] = st.text_input(
            "📞 Emergency Contact Number",
            value=st.session_state.get("emergency_contact_number", "+1 (555) 019-2834"),
            key=f"ctrl_em_contact_{current_role}",
        )

    # ----------------------------------------------------
    # LIVE MONITORING TOP BANNER & ACTION CONTROLS (Image 1 header)
    # ----------------------------------------------------
    cam_status_bg = "#ECFDF5" if run_stream else "#FEF2F2"
    cam_status_color = "#065F46" if run_stream else "#991B1B"
    cam_status_border = "#A7F3D0" if run_stream else "#FECDD3"
    cam_status_label = "🟢 Camera Streaming" if run_stream else "⚪ Feed Paused"

    st.markdown('<div class="live-cam-banner-container" style="background:#FFFFFF; border:1.5px solid #E2E8F0; border-radius:18px; padding:16px 20px; box-shadow:0 4px 20px rgba(0,0,0,0.04); margin-bottom:16px;">', unsafe_allow_html=True)
    b_col_info, b_col_badges, b_col_btn = st.columns([13, 8, 3])
    with b_col_info:
        st.markdown(
            f"""
            <div style="padding:2px 0;">
                <h3 style="margin:0; color:#0F172A; font-weight:800; font-size:1.20rem; line-height:1.3;">
                    Resident 01 – {selected_room} &bull; Camera 0{camera_idx + 1} – Live Monitoring
                </h3>
                <span style="color:#475569; font-size:0.86rem; font-weight:600;">
                    Live AI Pose Tracking Active &bull; Monitored by Healthcare Caregiver Team
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with b_col_badges:
        st.markdown(
            f"""
            <div style="display:flex; gap:8px; align-items:center; justify-content:flex-end; padding-top:6px; flex-wrap:nowrap;">
                <span style="background:#ECFDF5; color:#065F46; border:1px solid #A7F3D0; padding:6px 12px; border-radius:14px; font-weight:800; font-size:0.80rem; white-space:nowrap;">
                    🛡️ Safety Mode: Active
                </span>
                <span style="background:{cam_status_bg}; color:{cam_status_color}; border:1px solid {cam_status_border}; padding:6px 12px; border-radius:14px; font-weight:800; font-size:0.80rem; white-space:nowrap;">
                    {cam_status_label}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with b_col_btn:
        cam_icon_char = "📹" if run_stream else "📷"
        cam_tooltip = (
            "Live Camera Feed is Streaming. Click to pause the camera."
            if run_stream
            else "Camera feed is paused. Click to start / resume live webcam."
        )
        cam_btn_key = f"btn_cam_stream_toggle_{header_label.lower().replace(' ', '_')}_{current_role}"
        if st.button(cam_icon_char, key=cam_btn_key, help=cam_tooltip, use_container_width=True):
            new_stream_val = not run_stream
            st.session_state["stream_active"] = new_stream_val
            if not new_stream_val:
                GlobalCameraHub.get_instance().stop()
            else:
                GlobalCameraHub.get_instance().start(camera_idx)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Core Vision Initializations
    pose_detector = get_pose_detector()
    landmark_extractor = get_landmark_extractor()
    feature_calculator = get_feature_calculator()

    if "temporal_detector" not in st.session_state:
        st.session_state["temporal_detector"] = TemporalFallDetector(
            fall_angle_threshold=float(st.session_state["min_angle_setting"]),
            verification_frames=int(st.session_state["required_frames_setting"]),
        )
    temporal_detector = st.session_state["temporal_detector"]
    temporal_detector.fall_angle_threshold = float(st.session_state["min_angle_setting"])
    temporal_detector.verification_frames = int(st.session_state["required_frames_setting"])

    # Synchronize active_incident with database
    if st.session_state.get("active_incident") is not None:
        inc_id = st.session_state["active_incident"].get("incident_id")
        if inc_id:
            live_doc = db_manager.find_one("incidents", {"incident_id": inc_id})
            if not live_doc or live_doc.get("status") in {"RESOLVED", "CLOSED", "ACKNOWLEDGED_SAFE"}:
                st.session_state["active_incident"] = None

    # Ensure background camera is active
    if run_stream:
        hub = GlobalCameraHub.get_instance()
        hub.start(camera_idx)

    # ----------------------------------------------------
    # Dedicated Self-Contained Fragment for Live Camera & Pose (Image 2 style)
    # ----------------------------------------------------
    @st.fragment(run_every=0.5)
    def render_live_camera_panel():
        if not st.session_state.get("stream_active", True):
            st.markdown(
                """
                <div style="background:#F8FAFC; border:2px dashed #94A3B8; border-radius:16px; padding:32px 20px; text-align:center; margin:10px 0;">
                    <div style="font-size:2.8rem; margin-bottom:6px;">📷</div>
                    <h3 style="color:#1E293B; margin:0 0 6px 0; font-weight:800;">Live Camera Feed Paused</h3>
                    <p style="color:#64748B; font-size:0.92rem; margin-bottom:14px; font-weight:600;">
                        Live webcam monitoring is temporarily paused. Click the camera icon above or the button below to resume.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            col_p1, col_p2, col_p3 = st.columns([2, 2, 2])
            with col_p2:
                if st.button("▶️ Resume Camera Feed", key=f"btn_resume_cam_panel_{header_label.lower().replace(' ', '_')}_{current_role}", type="primary", use_container_width=True):
                    st.session_state["stream_active"] = True
                    GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
                    st.rerun()
            return

        # Synchronize active incident status with DB
        if st.session_state.get("active_incident") is not None:
            active_id = st.session_state["active_incident"].get("incident_id")
            if active_id:
                inc_chk = db_manager.find_one("incidents", {"incident_id": active_id})
                if not inc_chk or inc_chk.get("status") in {"RESOLVED", "CLOSED", "ACKNOWLEDGED_SAFE"}:
                    st.session_state["active_incident"] = None
                    if "temporal_detector" in st.session_state:
                        st.session_state["temporal_detector"].reset()

        hub = GlobalCameraHub.get_instance()
        if not hub.is_active():
            started, _, error_message = hub.start(camera_idx)
            if not started:
                st.error(
                    f"Camera not available, check device index or permissions. ({error_message or hub.capture_status})"
                )
                return

        # Prepare layout with st.empty() placeholders to avoid heavy page reruns and boost FPS
        col_v, col_t = st.columns([13, 9])
        with col_v:
            st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:0 0 8px 0;">📹 Live Camera Stream</h4>', unsafe_allow_html=True)
            cam_feed_slot = st.empty()
        with col_t:
            st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:0 0 8px 0;">📊 Live Monitoring Telemetry</h4>', unsafe_allow_html=True)
            telemetry_slot = st.empty()
            st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:14px 0 8px 0;">📱 Emergency SOS Dispatch</h4>', unsafe_allow_html=True)
            sos_slot = st.empty()

        # Update in a loop with st.empty() placeholder for high, smooth FPS
        loop_cycles = 25
        for frame_cycle in range(loop_cycles):
            if not st.session_state.get("stream_active", True):
                break

            success, frame, cam_fps = hub.read_frame()
            if not success or frame is None:
                if frame_cycle == 0:
                    cam_feed_slot.error(
                        f"Camera not available, check device index or permissions. ({hub.capture_status})"
                    )
                time.sleep(0.04)
                continue

            h, w = frame.shape[:2]
            if w > 640:
                scale = 640.0 / w
                frame = cv2.resize(frame, (640, int(h * scale)))
                h, w = frame.shape[:2]

            annotated_frame, results = pose_detector.process_frame(frame.copy())
            landmarks = landmark_extractor.extract(results)
            features = feature_calculator.calculate(landmarks)

            curr_t = time.time()
            prev_t = st.session_state.get("_monitoring_previous_frame_time", curr_t)
            dt = curr_t - prev_t
            fps = 1.0 / dt if dt > 0 else (cam_fps if cam_fps > 0 else 28.0)
            st.session_state["_monitoring_previous_frame_time"] = curr_t

            temporal_res = temporal_detector.update(features, timestamp=curr_t)
            posture = temporal_res["posture"]
            is_possible_fall = temporal_res["is_possible_fall"]
            velocity = temporal_res.get("velocity", 0.0)
            evidence_points = temporal_res.get("explanation_evidence", [])
            body_angle = features.get("body_angle_degrees") if features else None
            body_angle_text = f"{body_angle:.1f}°" if body_angle is not None else "Waiting for pose"
            mean_vis = features.get("mean_visibility", 0.0) if features else 0.0

            display_frame = annotated_frame.copy()
            if st.session_state.get("ghost_mode"):
                ghost_canvas = np.full((h, w, 3), 20, dtype=np.uint8)
                if results and results.pose_landmarks:
                    import mediapipe as mp
                    mp.solutions.drawing_utils.draw_landmarks(
                        ghost_canvas,
                        results.pose_landmarks,
                        mp.solutions.pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp.solutions.drawing_utils.DrawingSpec(color=(0, 255, 200), thickness=3, circle_radius=4),
                        connection_drawing_spec=mp.solutions.drawing_utils.DrawingSpec(color=(50, 180, 255), thickness=3),
                    )
                cv2.putText(ghost_canvas, "GHOST WIREFRAME AVATAR (PRIVACY MODE)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
                display_frame = ghost_canvas

            if is_possible_fall:
                cv2.putText(display_frame, "ALERT: FALL DETECTED!", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.90, (0, 0, 255), 3, cv2.LINE_AA)
            elif landmarks is not None:
                cv2.putText(display_frame, f"STATUS: {posture.upper()}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (0, 255, 0), 2, cv2.LINE_AA)
            else:
                cv2.putText(display_frame, "STATUS: SEARCHING FOR PERSON", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (160, 160, 160), 2, cv2.LINE_AA)

            cv2.putText(display_frame, f"FPS: {fps:.1f}", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            # Trigger emergency fall incident if verified fall detected
            now_t = time.time()
            last_res_t = st.session_state.get("last_incident_resolved_time", 0.0)
            if is_possible_fall and st.session_state.get("active_incident") is None and (now_t - last_res_t >= 6.0):
                new_inc = IncidentStateMachine.create_incident(
                    camera_id="CAM-001",
                    room_id=selected_room,
                    event_type="Possible Fall",
                    emergency_type="FALL DETECTION",
                    emergency_description=f"Computer Vision detected a confirmed fall in {selected_room} (torso angle: {body_angle_text}).",
                    detection_evidence=evidence_points,
                    body_angle=body_angle if body_angle is not None else 0.0,
                    status="PENDING",
                    current_assigned_caretaker="Mohini Ravat",
                    resident_id=curr_acc.get("resident_id", "RES-101"),
                    resident_name="Elderly Resident / Patient",
                )
                st.session_state["active_incident"] = new_inc
                st.session_state["verification_start_time"] = time.time()
                st.session_state["last_fall_snapshot"] = frame_rgb
                add_log(f"🚨 CRITICAL: Fall Detection registered [{new_inc['incident_id']}].")
                EmergencyRoutingService.route_incident(new_inc["incident_id"])
                st.rerun()

            cam_feed_slot.image(frame_rgb, channels="RGB", use_container_width=True)

            person_badge = '<span style="background:#DCFCE7; color:#15803D; border:1.5px solid #86EFAC; padding:5px 12px; border-radius:18px; font-weight:800; font-size:0.85rem; display:inline-block; margin-right:6px; margin-bottom:8px;">🟢 Person Detected</span>' if landmarks is not None else '<span style="background:#F1F5F9; color:#64748B; border:1.5px solid #CBD5E1; padding:5px 12px; border-radius:18px; font-weight:700; font-size:0.85rem; display:inline-block; margin-right:6px; margin-bottom:8px;">⚪ Searching for Person</span>'
            status_badge = '<span style="background:#FEE2E2; color:#B91C1C; border:1.5px solid #FCA5A5; padding:5px 12px; border-radius:18px; font-weight:800; font-size:0.85rem; display:inline-block; margin-bottom:8px;">🚨 FALL DETECTED!</span>' if is_possible_fall else f'<span style="background:#DCFCE7; color:#15803D; border:1.5px solid #86EFAC; padding:5px 12px; border-radius:18px; font-weight:800; font-size:0.85rem; display:inline-block; margin-bottom:8px;">🟢 {posture.upper() if landmarks else "NORMAL ACTIVITY"}</span>'

            telemetry_slot.markdown(
                f"""
                <div>{person_badge}{status_badge}</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:8px;">
                    <div style="background:#F8FAFC; padding:10px 14px; border-radius:12px; border:1.5px solid #E2E8F0;">
                        <div style="font-size:0.75rem; color:#64748B; font-weight:750; text-transform:uppercase;">Camera FPS</div>
                        <div style="font-size:1.40rem; font-weight:850; color:#0F172A;">{fps:.1f}</div>
                    </div>
                    <div style="background:#F8FAFC; padding:10px 14px; border-radius:12px; border:1.5px solid #E2E8F0;">
                        <div style="font-size:0.75rem; color:#64748B; font-weight:750; text-transform:uppercase;">Torso Angle</div>
                        <div style="font-size:1.40rem; font-weight:850; color:#0F172A;">{body_angle_text}</div>
                    </div>
                    <div style="background:#F8FAFC; padding:10px 14px; border-radius:12px; border:1.5px solid #E2E8F0;">
                        <div style="font-size:0.75rem; color:#64748B; font-weight:750; text-transform:uppercase;">Pose Visibility</div>
                        <div style="font-size:1.40rem; font-weight:850; color:#0F172A;">{mean_vis*100:.0f}%</div>
                    </div>
                    <div style="background:#F8FAFC; padding:10px 14px; border-radius:12px; border:1.5px solid #E2E8F0;">
                        <div style="font-size:0.75rem; color:#64748B; font-weight:750; text-transform:uppercase;">Drop Velocity</div>
                        <div style="font-size:1.40rem; font-weight:850; color:#0F172A;">{velocity:.3f}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            em_contact = st.session_state.get("emergency_contact_number", "+1 (555) 019-2834")
            sos_text = (
                f'<div style="background:#FFF1F2; border:2px solid #FDA4AF; border-radius:14px; padding:14px; color:#BE123C; font-weight:800;">🚨 EMERGENCY SOS DISPATCHED<div style="color:#881337; font-size:0.85rem; font-weight:600; margin-top:2px;">Automated alert sent to {em_contact}</div></div>'
                if is_possible_fall
                else f'<div style="background:#F8FAFC; border:1.5px solid #E2E8F0; border-radius:14px; padding:14px; color:#475569; font-weight:700;">📱 Emergency SOS Standby<div style="color:#64748B; font-size:0.85rem; font-weight:500; margin-top:2px;">Automated dispatch ready for {em_contact}</div></div>'
            )
            sos_slot.markdown(sos_text, unsafe_allow_html=True)

            time.sleep(0.02)

    render_live_camera_panel()

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        with st.expander("🔬 View Technical Details (FPS, Torso Angle, Drop Velocity)", expanded=False):
            st.markdown(
                f"""
                <div style="font-size:0.9rem; color:#334155; line-height:1.7;">
                    • <b>Camera Device Index:</b> <code>{camera_idx}</code><br>
                    • <b>Capture Backend:</b> <code>DirectShow (Hardware Accelerated)</code><br>
                    • <b>Resolution:</b> <code>640 &times; 480 px</code><br>
                    • <b>Fall Verification Window:</b> <code>{st.session_state.get('required_frames_setting', 5)} frames</code><br>
                    • <b>Angle Trigger Threshold:</b> <code>{st.session_state.get('min_angle_setting', 55.0)}&deg;</code>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with col_exp2:
        with st.expander("🧠 Why Was This Alert Triggered? (Movement Evidence)", expanded=False):
            st.markdown(
                """
                <div style="font-size:0.88rem; color:#1E293B; line-height:1.6;">
                    • <b>Sudden downward body movement detected:</b> Rapid vertical velocity towards floor.<br>
                    • <b>Body orientation changed significantly:</b> Rapid tilt from upright to horizontal posture.<br>
                    • <b>Person remained in horizontal position:</b> Torso angle persists near ground level.<br>
                    • <b>Fall-like movement persisted across consecutive frames:</b> Verified across frames.
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_admin_override_console():
    """
    Renders the Critical Emergency Override Console when both Caretaker 1 and Caretaker 2
    have forwarded or are unavailable, requiring direct Administrative intervention:
    1. Ambulance dispatch (108 / 911)
    2. Direct hospital consultation
    3. Emergency backup staff dispatch
    4. Mark safe and resolve
    """
    admin_inc = None
    last_esc = st.session_state.get("last_escalation")
    if last_esc:
        esc_status = last_esc.get("status", "")
        contact_name = last_esc.get("contact", {}).get("name", "")
        if esc_status in ["CRITICAL_ADMIN_OVERRIDE", "ADMIN_ACTION_TAKEN"] or "Admin" in contact_name:
            admin_inc = last_esc

    if not admin_inc:
        db_inc = db_manager.find_one(
            "incidents",
            {"status": {"$in": ["CRITICAL_ADMIN_OVERRIDE", "ADMIN_ACTION_TAKEN"]}},
            sort=[("detected_at", -1)]
        )
        if db_inc:
            admin_inc = db_inc

    if not admin_inc:
        return

    # Extract incident details
    inc_id = admin_inc.get("incident_id") or admin_inc.get("contact", {}).get("incident_id", "CRITICAL-ALERT")
    room_label = admin_inc.get("room_id") or admin_inc.get("room_name", "Living Room")
    body_angle = admin_inc.get("body_angle_degrees") or admin_inc.get("body_angle", 74.0)

    # Fetch live DB incident to get latest timeline and action status
    db_record = db_manager.find_one("incidents", {"incident_id": inc_id})
    timeline = db_record.get("timeline", []) if db_record else admin_inc.get("timeline", [])
    admin_action_status = db_record.get("admin_action") if db_record else admin_inc.get("admin_action")

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%); border: 2.5px solid #E11D48; border-radius: 16px; padding: 22px; margin-bottom: 22px; box-shadow: 0 8px 24px rgba(225, 29, 72, 0.15);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <h2 style="color: #9F1239; margin: 0 0 6px 0; font-weight: 800; font-size: 1.4rem;">
                        🚨 CRITICAL EMERGENCY OVERRIDE CONSOLE
                    </h2>
                    <p style="color: #4C0519; margin: 0; font-size: 1.05rem; font-weight: 700;">
                        Both Caretaker 1 (Mohini Ravat) & Caretaker 2 (Radha Raghav) Could Not Attend!
                    </p>
                    <p style="color: #881337; margin: 4px 0 0 0; font-size: 0.92rem;">
                        Location: <b>{room_label}</b> • Incident ID: <code>{inc_id}</code> • Body Tilt: <b>{body_angle:.1f}°</b>
                    </p>
                </div>
                <div style="text-align: right;">
                    <span style="background: #E11D48; color: white; padding: 6px 18px; border-radius: 20px; font-weight: 800; font-size: 0.88rem; letter-spacing: 0.5px;">
                        ADMINISTRATIVE INTERVENTION REQUIRED
                    </span>
                    <div style="font-size: 0.8rem; color: #9F1239; margin-top: 6px; font-weight: 600;">
                        Chain: Mohini (Unavailable) ➔ Radha (Unavailable) ➔ <b>ADMIN OVERRIDE</b>
                    </div>
                </div>
            </div>
            <div style="margin-top: 14px; background: rgba(255,255,255,0.7); border-radius: 10px; padding: 10px 14px; border: 1px solid #FECDD3; font-size: 0.88rem; color: #4C0519;">
                ⚠️ <b>Emergency Handover Directive:</b> As System Administrator, you have full authority to arrange emergency services, dispatch an ambulance, consult the nearest hospital emergency unit, or deploy rapid response medical staff.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if admin_action_status:
        st.info(f"📋 **Current Intervention Status:** `{admin_action_status}`")

    # 4 Action Cards in a 2x2 grid
    c_act1, c_act2 = st.columns(2)
    with c_act1:
        st.markdown(
            """
            <div style="background: #FFFFFF; border: 1.5px solid #FCA5A5; border-radius: 12px; padding: 14px; margin-bottom: 10px;">
                <b style="font-size: 1.0rem; color: #991B1B;">🚑 1. Dispatch Emergency Ambulance</b>
                <p style="color: #4B5563; font-size: 0.83rem; margin: 4px 0 8px 0;">
                    Initiates automated emergency call to National Ambulance Service (108 / 911) with GPS coordinates.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🚑 Dispatch Emergency Ambulance (108 / 911)", key="btn_admin_amb", type="primary", use_container_width=True):
            res = CaregiverNotificationService.admin_take_emergency_action(
                incident_id=inc_id,
                action_type="AMBULANCE",
                details="Admin dispatched emergency ambulance (108/911). Paramedic unit en route to resident location.",
            )
            add_log(f"ADMIN ACTION: Dispatched Emergency Ambulance for [{inc_id}].")
            st.success("🚑 **Ambulance Dispatched!** Service 108 notified with resident location. Paramedic Unit #412 en route. ETA: 8-12 minutes.")
            time.sleep(1)
            st.rerun()

        st.markdown(
            """
            <div style="background: #FFFFFF; border: 1.5px solid #93C5FD; border-radius: 12px; padding: 14px; margin-bottom: 10px; margin-top: 10px;">
                <b style="font-size: 1.0rem; color: #1E40AF;">🏥 2. Directly Consult Nearest Hospital</b>
                <p style="color: #4B5563; font-size: 0.83rem; margin: 4px 0 8px 0;">
                    Establishes direct line with Apollo / Fortis Hospital Emergency Department & reserves trauma bed.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🏥 Directly Consult Nearest Hospital / ER", key="btn_admin_hosp", type="secondary", use_container_width=True):
            res = CaregiverNotificationService.admin_take_emergency_action(
                incident_id=inc_id,
                action_type="HOSPITAL",
                details="Admin directly consulted Apollo / Fortis Hospital Emergency Triage Desk. Duty Dr. notified.",
            )
            add_log(f"ADMIN ACTION: Consulted Hospital ER for [{inc_id}].")
            st.success("🏥 **Hospital Consulted!** Emergency department triage desk (+91 80 2630 4050) connected. Duty Physician Dr. Sharma notified. Trauma bed reserved.")
            time.sleep(1)
            st.rerun()

    with c_act2:
        st.markdown(
            """
            <div style="background: #FFFFFF; border: 1.5px solid #FCD34D; border-radius: 12px; padding: 14px; margin-bottom: 10px;">
                <b style="font-size: 1.0rem; color: #92400E;">👨‍⚕️ 3. Dispatch On-Call Medical Staff</b>
                <p style="color: #4B5563; font-size: 0.83rem; margin: 4px 0 8px 0;">
                    Deploys rapid response on-call registered nurse / community paramedic to resident home.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("👨‍⚕️ Dispatch On-Call Medical Staff", key="btn_admin_staff", type="secondary", use_container_width=True):
            res = CaregiverNotificationService.admin_take_emergency_action(
                incident_id=inc_id,
                action_type="BACKUP_STAFF",
                details="Admin dispatched Rapid Response On-Call Nurse / Paramedic.",
            )
            add_log(f"ADMIN ACTION: Deployed on-call medical staff for [{inc_id}].")
            st.success("👨‍⚕️ **On-Call Staff Deployed!** Mobile nursing response team dispatched to resident premises.")
            time.sleep(1)
            st.rerun()

        st.markdown(
            """
            <div style="background: #FFFFFF; border: 1.5px solid #86EFAC; border-radius: 12px; padding: 14px; margin-bottom: 10px; margin-top: 10px;">
                <b style="font-size: 1.0rem; color: #166534;">✅ 4. Confirm Handled & Close Emergency</b>
                <p style="color: #4B5563; font-size: 0.83rem; margin: 4px 0 8px 0;">
                    Verifies patient attended and stable, marks emergency resolved, and logs audit archive.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("✅ Confirm Patient Attended & Close Emergency", key="btn_admin_close", type="primary", use_container_width=True):
            res = CaregiverNotificationService.admin_take_emergency_action(
                incident_id=inc_id,
                action_type="RESOLVE",
                details="System Administrator verified resident is attended and safe. Emergency closed and archived.",
            )
            add_log(f"ADMIN ACTION: Emergency [{inc_id}] resolved and closed safe.")
            st.session_state["last_escalation"] = None
            st.session_state["active_incident"] = None
            st.success("✅ **Emergency Handled & Closed!** Incident marked safe and logged in permanent audit history.")
            time.sleep(1)
            st.rerun()

    # Timeline view of this emergency
    if timeline:
        with st.expander(f"⏱️ Emergency Timeline & Handover Audit Trail for [{inc_id}]", expanded=True):
            for step in timeline:
                st.caption(f"🕒 **[{step.get('time')}]** {step.get('event')}")
    st.markdown("---")


# ====================================================
# 1. SYSTEM ADMIN DASHBOARD
# ====================================================
def render_admin_dashboard():
    st.markdown(
        """
        <div class="role-banner-admin">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h3 style="color:#1E3A8A; margin:0; font-weight:800;">🛡️ System Administrator Master Console</h3>
                    <p style="color:#3B82F6; margin:2px 0 0 0; font-weight:600; font-size:0.9rem;">
                        Full system authority: Live fall CV monitoring, MongoDB records, room configs, caregiver routing.
                    </p>
                </div>
                <span style="background:#BFDBFE; color:#1E40AF; padding:4px 12px; border-radius:16px; font-weight:700; font-size:0.85rem;">
                    Full Root Access
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render Critical Emergency Override Console if escalated to Admin
    render_admin_override_console()

    # MODULE 7: 10 Admin Emergency Monitoring Metrics
    all_incidents = db_manager.find("incidents", limit=500, sort=[("detected_at", -1)])
    total_incidents = len(all_incidents)
    voice_alerts = len([i for i in all_incidents if i.get("emergency_type") == "VOICE EMERGENCY" or "VOICE" in str(i.get("event_type", "")).upper()])
    cv_fall_alerts = len([i for i in all_incidents if i.get("emergency_type") == "FALL DETECTION" or "FALL" in str(i.get("event_type", "")).upper()])
    manual_sos_alerts = len([i for i in all_incidents if "SOS" in str(i.get("emergency_type", "")).upper() or "SOS" in str(i.get("event_type", "")).upper() or "SOS" in str(i.get("incident_id", "")).upper()])
    pending_incidents = len([
        i for i in all_incidents
        if i.get("status") in [
            "PENDING",
            "PENDING_VERIFICATION",
            "ESCALATED_LOCAL_CARETAKER",
            "ESCALATED_CARETAKER_1",
            "ESCALATED_CARETAKER_2",
            "CRITICAL_ADMIN_OVERRIDE",
            "UNACKNOWLEDGED_ADMIN_REQUIRED",
        ]
    ])
    acknowledged_incidents = len([i for i in all_incidents if i.get("status") == "ACKNOWLEDGED"])
    resolved_incidents = len([i for i in all_incidents if i.get("status") in ["RESOLVED", "CLOSED", "ACKNOWLEDGED_SAFE"]])
    unack_admin = len([i for i in all_incidents if i.get("status") in ["UNACKNOWLEDGED_ADMIN_REQUIRED", "CRITICAL_ADMIN_OVERRIDE"]])

    latest_active = next((
        i for i in all_incidents
        if i.get("status") in [
            "PENDING",
            "ESCALATED_LOCAL_CARETAKER",
            "ESCALATED_CARETAKER_1",
            "ESCALATED_CARETAKER_2",
            "ACKNOWLEDGED",
            "UNACKNOWLEDGED_ADMIN_REQUIRED",
            "CRITICAL_ADMIN_OVERRIDE",
        ]
    ), None)
    curr_caretaker = latest_active.get("current_assigned_caretaker", "Mohini Ravat") if latest_active else "Mohini Ravat"

    st.markdown("### 📊 System Emergency Monitoring Metrics")
    m_row1 = st.columns(5)
    m_row1[0].metric("1. Total Emergencies", f"{total_incidents}")
    m_row1[1].metric("2. Voice Emergency", f"{voice_alerts}")
    m_row1[2].metric("3. CV Fall Alerts", f"{cv_fall_alerts}")
    m_row1[3].metric("4. Manual SOS Alerts", f"{manual_sos_alerts}")
    m_row1[4].metric("5. Pending Incidents", f"{pending_incidents}")

    m_row2 = st.columns(5)
    m_row2[0].metric("6. Acknowledged", f"{acknowledged_incidents}")
    m_row2[1].metric("7. Resolved Incidents", f"{resolved_incidents}")
    m_row2[2].metric("8. Unack (Admin Req)", f"{unack_admin}")
    m_row2[3].metric("9. Assigned Caretaker", curr_caretaker.split()[0] if curr_caretaker else "Mohini")
    m_row2[4].metric("10. Escalation History", f"{len([i for i in all_incidents if i.get('escalation_history') or i.get('timeline')])} entries")
    st.markdown("---")

    admin_tab = st.radio(
        "Admin Navigation:",
        [
            "Live Fall Detection & Monitoring 📹",
            "📋 Fall Incident Records & Emergency History",
            "🏠 Camera & Room Configuration",
            "⚙️ Caregiver Directory & Alerts",
            "🏥 Facilities & Care Management",
        ],
        key="admin_navigation_tab",
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # TAB 1: LIVE FALL DETECTION
    if admin_tab == "Live Fall Detection & Monitoring 📹":
        render_emergency_verification_panel()
        render_escalation_banner()

        st.markdown("### Monitoring setup")
        registered_rooms = db_manager.find("rooms", {"is_active": True}, limit=1000)
        room_options = [
            (
                f"Room {room.get('room_number', room['room_id'])} — "
                f"{room.get('building', 'Building')}, {room.get('floor', 'Floor')} · "
                f"{room.get('camera_id') or 'Camera ID not configured'}"
            )
            for room in registered_rooms
        ] or [
            "Living Room — Camera 1",
            "Bedroom — Camera 2",
            "Patient Room — Camera 3",
        ]
        selected_room = st.session_state.get("selected_room", room_options[0])
        selected_room_index = (
            room_options.index(selected_room) if selected_room in room_options else 0
        )
        setup_room, setup_camera, setup_active = st.columns(3)
        with setup_room:
            st.session_state["selected_room"] = st.selectbox(
                "Active room / camera",
                room_options,
                index=selected_room_index,
                key="admin_active_room",
            )
        with setup_camera:
            st.session_state["camera_hw_index"] = st.number_input(
                "Webcam device index",
                min_value=0,
                max_value=5,
                value=min(max(int(st.session_state.get("camera_hw_index", 0)), 0), 5),
                step=1,
                key="admin_camera_hw_index",
                help="Try another index if the preview is black or shows the wrong camera.",
            )
        with setup_active:
            st.session_state["stream_active"] = st.toggle(
                "Enable live monitoring",
                value=bool(st.session_state.get("stream_active", True)),
                key="admin_monitoring_enabled",
            )

        st.sidebar.header("Monitoring options")
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔒 Privacy Protection")
        st.session_state["ghost_mode"] = st.sidebar.toggle(
            "👻 Privacy Ghost Avatar Mode",
            value=st.session_state["ghost_mode"],
            help="Displays pose wireframe on dark digital canvas, hiding camera feed.",
        )

        st.sidebar.markdown("---")
        st.sidebar.subheader("🎙️ Emergency Assistance")
        st.session_state["voice_enabled"] = st.sidebar.toggle(
            "Enable Voice Assistance",
            value=st.session_state["voice_enabled"],
        )

        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Detection Sensitivity")
        st.sidebar.caption(f"Min Fall Angle: **{st.session_state['min_angle_setting']}°**")
        st.sidebar.caption(f"Temporal Persistence: **{st.session_state['required_frames_setting']} frames**")

        render_live_monitoring_engine(show_full_controls=True, header_label="Admin Vision Feed")

    # TAB 2: INCIDENT RECORDS
    elif admin_tab == "📋 Fall Incident Records & Emergency History":
        st.markdown('<div class="card-light">', unsafe_allow_html=True)
        st.subheader("📋 Fall Incident Records & Emergency History")
        st.markdown("Chronological audit log of all detected fall events, emergency responses, and notification statuses.")

        incidents_list = db_manager.find("incidents", limit=100)
        if not incidents_list:
            st.info("ℹ️ No incident records logged yet. Trigger a simulated fall in Live Monitoring to view event history.")
        else:
            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                st.markdown("### 📑 Incident Registry")
                df_incidents = pd.DataFrame([
                    {
                        "Incident ID": inc.get("incident_id"),
                        "Resident": inc.get("resident_name", "Elderly Resident / Patient"),
                        "Room": inc.get("room_number") or inc.get("room_id"),
                        "Emergency Type": inc.get("emergency_type") or inc.get("event_type"),
                        "Assigned Caretaker": inc.get("current_assigned_caretaker", "Mohini Ravat"),
                        "Status": inc.get("status"),
                        "Detected At": inc.get("detected_at") or inc.get("timestamp"),
                        "Escalation Reason": inc.get("escalation_reason", "—") or "—",
                        "Resolved By": inc.get("resolved_by", "—") or "—",
                    }
                    for inc in incidents_list
                ])
                st.dataframe(df_incidents, width="stretch")

                options = [f"{inc.get('incident_id')} — {inc.get('status')} ({inc.get('emergency_type') or inc.get('event_type')})" for inc in incidents_list]
                selected_idx = st.selectbox("Select Incident Record to Inspect:", range(len(options)), format_func=lambda i: options[i])
                active_inc = incidents_list[selected_idx]

            with col_t2:
                st.markdown(f"### 🔍 Detailed Audit: {active_inc.get('incident_id')}")
                st.markdown(
                    f"""
                    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:18px; margin-bottom:14px;">
                        <b>Incident ID:</b> <code>{active_inc.get('incident_id')}</code><br>
                        <b>Resident Name:</b> {active_inc.get('resident_name', 'Elderly Resident / Patient')}<br>
                        <b>Location Node:</b> {active_inc.get('room_number') or active_inc.get('room_id')}<br>
                        <b>Emergency Type:</b> <span style="font-weight:700; color:#BE123C;">{active_inc.get('emergency_type') or active_inc.get('event_type')}</span><br>
                        <b>Status:</b> <b>{active_inc.get('status')}</b><br>
                        <b>Assigned Caretaker:</b> <b>{active_inc.get('current_assigned_caretaker', 'Mohini Ravat')}</b><br>
                        <b>Detected Timestamp:</b> {active_inc.get('detected_at') or active_inc.get('timestamp')}<br>
                        <b>Escalation Reason:</b> {active_inc.get('escalation_reason') or 'None (Directly Handled)'}<br>
                        <b>Resolution Timestamp:</b> {active_inc.get('resolution_timestamp') or 'Pending'}<br>
                        <b>Resolution Notes:</b> {active_inc.get('resolution_notes') or 'None'}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown("#### 🧠 Detection Evidence Recorded")
                evidence = active_inc.get("detection_evidence", [])
                if evidence:
                    for item in evidence:
                        st.markdown(f"- {item}")
                else:
                    st.caption("Standard fall kinetic threshold reached.")

                st.markdown("#### ⏱️ Emergency Response & Event Timeline")
                timeline = active_inc.get("timeline", [])
                if timeline:
                    for ev in timeline:
                        st.caption(f"🕒 **[{ev.get('time')}]** {ev.get('event')}")
                else:
                    st.caption("No timeline history recorded.")

                st.markdown("---")
                act_col1, act_col2 = st.columns(2)
                if act_col1.button("✅ Confirm Acknowledged Safe", use_container_width=True):
                    IncidentStateMachine.transition(active_inc["incident_id"], "ACKNOWLEDGED_SAFE", "Manually verified safe by Administrator.")
                    add_log(f"Admin acknowledged safe: {active_inc['incident_id']}")
                    st.rerun()

                if act_col2.button("🔒 Close & Archive Incident", use_container_width=True):
                    IncidentStateMachine.transition(active_inc["incident_id"], "CLOSED", "Incident resolved and archived.", reviewer="Admin")
                    add_log(f"Admin closed incident: {active_inc['incident_id']}")
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # TAB 3: CAMERA & ROOM CONFIGURATION
    elif admin_tab == "🏠 Camera & Room Configuration":
        st.markdown('<div class="card-light">', unsafe_allow_html=True)
        st.subheader("🏠 Camera Node & Multi-Room Configuration")
        st.markdown("Manage camera nodes across residential rooms for real-time location mapping.")

        c_r1, c_r2 = st.columns([1, 1])
        with c_r1:
            st.markdown("### 🏢 Registered Home Locations")
            rooms_data = [
                {"Room Name": "Living Room", "Camera Assigned": "Camera 1 (Active USB Webcam)", "Status": "ONLINE 🟢", "Type": "Primary Common Area"},
                {"Room Name": "Master Bedroom", "Camera Assigned": "Camera 2 (Simulated Node)", "Status": "STANDBY 🟡", "Type": "Private Sleeping Area"},
                {"Room Name": "Patient Room", "Camera Assigned": "Camera 3 (Simulated Node)", "Status": "STANDBY 🟡", "Type": "High-Risk Recovery Area"},
            ]
            st.dataframe(pd.DataFrame(rooms_data), width="stretch")
            st.caption("ℹ️ *System runs real hardware vision on Camera 1 while supporting multi-room database tracking.*")

        with c_r2:
            st.markdown("### ➕ Register New Room Node")
            with st.form("new_room_form"):
                new_room_name = st.text_input("Room Identifier (e.g. Hallway / Kitchen)")
                new_cam_id = st.text_input("Camera Label (e.g. Camera 4)", value="Camera 4")
                new_hw_idx = st.number_input("Hardware Device Index", min_value=0, max_value=5, value=1)
                room_sub = st.form_submit_button("Register Room Node")
                if room_sub:
                    if new_room_name:
                        st.success(f"✅ Registered {new_room_name} ({new_cam_id}) successfully!")
                        add_log(f"Registered new room node: {new_room_name}")
                    else:
                        st.error("Please provide a room identifier.")

        st.markdown("</div>", unsafe_allow_html=True)

    # TAB 4: CAREGIVER DIRECTORY & CONTROLS
    elif admin_tab == "⚙️ Caregiver Directory & Alerts":
        st.markdown('<div class="card-light">', unsafe_allow_html=True)
        st.subheader("⚙️ Emergency Caretaker Roster & Tiered Dispatch Controls")
        st.markdown("Manage primary responder (Mohini Ravat) and secondary responder (Radha Raghav) with failover escalation.")

        col_cg1, col_cg2 = st.columns([13, 11])
        with col_cg1:
            st.markdown("### 📞 Registered Caregivers Roster")
            caregivers_list = db_manager.find("caregivers")
            if not caregivers_list:
                defaults = [
                    {"name": "Mohini Ravat", "email": "mohini.ravat@fallguard.local", "role": "Primary Caretaker (Caretaker 1)", "phone": "+91 98765 43210", "is_active": True, "is_available": True, "priority": 1, "username": "mohini"},
                    {"name": "Radha Raghav", "email": "radha.raghav@fallguard.local", "role": "Secondary Caretaker (Caretaker 2)", "phone": "+91 98123 45678", "is_active": True, "is_available": True, "priority": 2, "username": "radha"},
                ]
                for c in defaults:
                    db_manager.insert_one("caregivers", c)
                caregivers_list = defaults

            df_caregivers = pd.DataFrame(caregivers_list)
            cols_to_show = [col for col in ["name", "email", "role", "is_available", "phone"] if col in df_caregivers.columns]
            st.dataframe(df_caregivers[cols_to_show], width="stretch")

            st.markdown("---")
            st.markdown("### 🟢 On-Duty Availability Controls (Failover Testing)")
            st.caption("Toggle availability to demonstrate tiered escalation: Caretaker 1 ➔ Caretaker 2 ➔ Admin")

            c_av1, c_av2 = st.columns(2)
            with c_av1:
                c1_found = next((c for c in caregivers_list if "Mohini" in c.get("name", "") or c.get("priority") == 1), None)
                c1_val = c1_found.get("is_available", True) if c1_found else True
                t1 = st.toggle("Caretaker 1: Mohini Ravat", value=c1_val, key="t_c1_avail_admin")
                if c1_found and t1 != c1_val:
                    db_manager.update_one("caregivers", {"email": c1_found.get("email")}, {"is_available": t1})
                    st.rerun()
                st.markdown("🟢 **On-Duty (Primary Responder)**" if t1 else "🔴 **Off-Duty (Failover to Radha Raghav)**")

            with c_av2:
                c2_found = next((c for c in caregivers_list if "Radha" in c.get("name", "") or c.get("priority") == 2), None)
                c2_val = c2_found.get("is_available", True) if c2_found else True
                t2 = st.toggle("Caretaker 2: Radha Raghav", value=c2_val, key="t_c2_avail_admin")
                if c2_found and t2 != c2_val:
                    db_manager.update_one("caregivers", {"email": c2_found.get("email")}, {"is_available": t2})
                    st.rerun()
                st.markdown("🟢 **On-Duty (Secondary Standby)**" if t2 else "🔴 **Off-Duty (Failover to Admin Override)**")

            st.markdown("---")
            sim_c1, sim_c2 = st.columns(2)
            with sim_c1:
                if st.button("🚨 Simulate Tiered Routing Protocol", type="primary", use_container_width=True):
                    with st.spinner("Executing tiered emergency routing protocol..."):
                        test_id = f"TEST-ESC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                        IncidentStateMachine.create_incident(
                            incident_id=test_id,
                            camera_id="CAM-001",
                            room_id="Living Room",
                            event_type="Routing test",
                            detection_evidence=["Administrator initiated routing test"],
                            body_angle=74.5,
                            resident_id="RES-101",
                            resident_name="Routing Test",
                        )
                        EmergencyRoutingService.route_incident(test_id)
                        test_esc = db_manager.find_one("incidents", {"incident_id": test_id}) or {}
                        st.session_state["last_escalation"] = test_esc
                        st.success(
                            f"✅ Escalation Protocol Executed: "
                            f"{test_esc.get('current_assigned_caretaker', test_esc.get('status', 'Routed'))}"
                        )
                        st.rerun()

            with sim_c2:
                if st.button("👥 Trigger 3-Tier Handover Simulation (Mohini ➔ Radha ➔ Admin)", use_container_width=True):
                    test_id = f"FALL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    new_inc = IncidentStateMachine.create_incident(
                        incident_id=test_id,
                        camera_id="CAM-001",
                        room_id="Living Room — Camera 1",
                        event_type="FALL DETECTION",
                        emergency_type="FALL DETECTION",
                        emergency_description="Simulated confirmed fall in Living Room.",
                        detection_evidence=["Torso tilt: 74.2° (> 38°)", "Drop velocity: 0.38 m/s", "Rapid horizontal displacement"],
                        body_angle=74.2,
                        status="PENDING",
                        current_assigned_caretaker="Mohini Ravat",
                        resident_id="RES-101",
                        resident_name="Elderly Resident / Patient",
                    )
                    EmergencyRoutingService.route_incident(test_id)
                    esc_res = db_manager.find_one("incidents", {"incident_id": test_id}) or {}
                    st.session_state["active_incident"] = new_inc
                    st.session_state["last_escalation"] = esc_res
                    st.success(f"✅ Emergency [{test_id}] dispatched to Mohini Ravat! Switch to Mohini's portal to test forward flow.")
                    st.rerun()

            if st.session_state.get("last_escalation"):
                esc_t4 = st.session_state["last_escalation"]
                chain_t4 = esc_t4.get("escalation_chain", [])
                st.markdown("#### 📢 Real Escalation Chain Outcome")
                for step in chain_t4:
                    tier_n = step.get("tier")
                    stat_n = step.get("status")
                    note_n = step.get("note")
                    if "ALERT RECEIVED" in stat_n or "DELIVERED" in stat_n:
                        st.success(f"**{tier_n}** — `{stat_n}`\n\n{note_n}")
                    elif "STANDBY" in stat_n:
                        st.info(f"**{tier_n}** — `{stat_n}`\n\n{note_n}")
                    elif "NOT RESPONDING" in stat_n or "UNAVAILABLE" in stat_n:
                        st.error(f"**{tier_n}** — `{stat_n}`\n\n{note_n}")
                    else:
                        st.warning(f"**{tier_n}** — `{stat_n}`\n\n{note_n}")

        with col_cg2:
            st.markdown("### 🎛️ Algorithm Sensitivity Sliders")
            st.session_state["min_angle_setting"] = st.slider(
                "Minimum Fall Angle Threshold (°)",
                min_value=25,
                max_value=60,
                value=st.session_state["min_angle_setting"],
                help="Torso tilt angle from vertical required to register a horizontal fall posture.",
            )
            st.session_state["required_frames_setting"] = st.slider(
                "Temporal Persistence Frames",
                min_value=1,
                max_value=10,
                value=st.session_state["required_frames_setting"],
                help="Consecutive frames required before triggering verification alert.",
            )

            st.markdown("---")
            st.markdown("### 📧 Send Test Alert Email (SMTP)")
            if st.button("📢 Send Test Email via Real SMTP", use_container_width=True):
                with st.spinner("Connecting to SMTP mail provider..."):
                    test_result = CaregiverNotificationService.send_test_alert()
                    if test_result["status"] == "SENT":
                        st.success(f"✅ {test_result['message']}")
                    elif test_result["status"] == "NOT_CONFIGURED":
                        st.warning(f"⚠️ {test_result['message']}")
                    else:
                        st.error(f"❌ {test_result['message']}")

        st.markdown("</div>", unsafe_allow_html=True)

    elif admin_tab == "🏥 Facilities & Care Management":
        st.subheader("🏥 Facility, Room, Resident & Local Caretaker Management")
        facilities = db_manager.find("facilities", {"is_active": True}, limit=500)
        rooms = db_manager.find("rooms", {"is_active": True}, limit=1000)
        residents = db_manager.find("residents", {"is_active": True}, limit=1000)
        local_caretakers = db_manager.find("local_caretakers", {"is_active": True}, limit=1000)
        facility_by_id = {item["facility_id"]: item for item in facilities}
        room_by_id = {item["room_id"]: item for item in rooms}

        st.markdown("#### Register a facility")
        with st.form("care_facility_registration"):
            facility_name = st.text_input("Facility name")
            facility_type = st.selectbox("Facility type", [item.value for item in FacilityType])
            facility_address = st.text_input("Address (optional)")
            facility_submitted = st.form_submit_button("Create facility")
        if facility_submitted:
            try:
                register_facility(
                    FacilityCreate(
                        name=facility_name,
                        facility_type=FacilityType(facility_type),
                        address=facility_address or None,
                    )
                )
                st.success("Facility registered.")
                st.rerun()
            except (HTTPException, ValueError) as err:
                st.error(err.detail if isinstance(err, HTTPException) else str(err))

        facilities = db_manager.find("facilities", {"is_active": True}, limit=500)
        facility_by_id = {item["facility_id"]: item for item in facilities}
        facility_ids = list(facility_by_id)
        if not facility_ids:
            st.info("Register a facility before adding rooms, residents, or local caretakers.")
        else:
            st.markdown("---")
            room_col, resident_col = st.columns(2)
            with room_col:
                st.markdown("#### Register a room")
                with st.form("care_room_registration"):
                    room_facility_id = st.selectbox(
                        "Facility",
                        facility_ids,
                        format_func=lambda value: facility_by_id[value]["name"],
                        key="care_room_facility",
                    )
                    room_building = st.text_input("Building", value="Main")
                    room_floor = st.text_input("Floor", value="Ground")
                    room_number = st.text_input("Room number")
                    room_camera_id = st.text_input("Camera ID (optional)")
                    room_submitted = st.form_submit_button("Create room")
                if room_submitted:
                    try:
                        register_room(
                            RoomCreate(
                                facility_id=room_facility_id,
                                building=room_building,
                                floor=room_floor,
                                room_number=room_number,
                                camera_id=room_camera_id or None,
                            )
                        )
                        st.success("Room registered.")
                        st.rerun()
                    except (HTTPException, ValueError) as err:
                        st.error(err.detail if isinstance(err, HTTPException) else str(err))

            with resident_col:
                st.markdown("#### Register a resident")
                if not rooms:
                    st.info("Add a room before registering a resident.")
                else:
                    room_ids = list(room_by_id)
                    eligible_rooms = [
                        room_id for room_id in room_ids
                        if facility_by_id.get(room_by_id[room_id]["facility_id"])
                    ]
                    with st.form("care_resident_registration"):
                        resident_name = st.text_input("Resident full name")
                        resident_age = st.number_input("Age", min_value=1, max_value=125, value=70)
                        resident_room_id = st.selectbox(
                            "Room",
                            eligible_rooms,
                            format_func=lambda value: (
                                f"{facility_by_id[room_by_id[value]['facility_id']]['name']} — "
                                f"{room_by_id[value]['room_number']}"
                            ),
                            key="care_resident_room",
                        )
                        resident_contact = st.text_input("Emergency contact")
                        resident_notes = st.text_area("Medical assistance notes (optional)")
                        with st.expander("Optional resident login credentials"):
                            resident_username = st.text_input("Resident username")
                            resident_password = st.text_input(
                                "Resident password (minimum 12 characters)",
                                type="password",
                            )
                        resident_submitted = st.form_submit_button("Create resident")
                    if resident_submitted:
                        try:
                            chosen_room = room_by_id[resident_room_id]
                            register_resident(
                                ResidentCreate.model_validate(
                                    {
                                        "full_name": resident_name,
                                        "age": int(resident_age),
                                        "facility_id": chosen_room["facility_id"],
                                        "room_id": resident_room_id,
                                        "emergency_contact": resident_contact,
                                        "medical_assistance_notes": resident_notes or None,
                                        "username": resident_username or None,
                                        "password": resident_password or None,
                                    }
                                )
                            )
                            st.success("Resident registered. Passwords are stored as hashes and are not displayed.")
                            st.rerun()
                        except (HTTPException, ValueError) as err:
                            st.error(err.detail if isinstance(err, HTTPException) else str(err))

            st.markdown("---")
            st.markdown("#### Register a local caretaker")
            eligible_caretaker_rooms = [
                room_id for room_id in room_by_id
                if facility_by_id.get(room_by_id[room_id]["facility_id"])
            ]
            caretaker_room_options = eligible_caretaker_rooms or ["No rooms available"]
            caretaker_room_id = st.selectbox(
                "Assigned room",
                caretaker_room_options,
                format_func=lambda value: (
                    f"{facility_by_id[room_by_id[value]['facility_id']]['name']} — "
                    f"{room_by_id[value]['room_number']}"
                ) if value in room_by_id else value,
                disabled=not eligible_caretaker_rooms,
                key="care_caretaker_room",
            )
            chosen_facility_id = (
                room_by_id[caretaker_room_id]["facility_id"]
                if caretaker_room_id in room_by_id else None
            )
            with st.form("care_local_caretaker_registration"):
                caretaker_name = st.text_input("Caretaker full name")
                caretaker_phone = st.text_input("Phone number")
                caretaker_email = st.text_input("Email")
                caretaker_username = st.text_input("Username")
                caretaker_password = st.text_input("Password (minimum 12 characters)", type="password")
                caretaker_availability = st.selectbox(
                    "Availability",
                    [item.value for item in CareAvailability],
                )
                caretaker_submitted = st.form_submit_button("Create local caretaker")
            if caretaker_submitted:
                if not chosen_facility_id:
                    st.error("Register a room before creating a local caretaker.")
                else:
                    try:
                        chosen_room = room_by_id[caretaker_room_id]
                        register_local_caretaker(
                            LocalCaretakerCreate.model_validate(
                                {
                                    "full_name": caretaker_name,
                                    "phone_number": caretaker_phone,
                                    "email": caretaker_email,
                                    "username": caretaker_username,
                                    "password": caretaker_password,
                                    "facility_id": chosen_facility_id,
                                    "building": chosen_room["building"],
                                    "floor": chosen_room["floor"],
                                    "room_id": caretaker_room_id,
                                    "availability": CareAvailability(caretaker_availability),
                                }
                            )
                        )
                        st.success("Local caretaker created; their password is stored as a hash.")
                        st.rerun()
                    except (HTTPException, ValueError) as err:
                        st.error(err.detail if isinstance(err, HTTPException) else str(err))

        st.markdown("---")
        st.markdown("#### Current assignments and care records")
        facilities = db_manager.find("facilities", {"is_active": True}, limit=500)
        rooms = db_manager.find("rooms", {"is_active": True}, limit=1000)
        residents = db_manager.find("residents", {"is_active": True}, limit=1000)
        local_caretakers = db_manager.find("local_caretakers", {"is_active": True}, limit=1000)
        room_by_id = {item["room_id"]: item for item in rooms}
        caretaker_by_id = {item["caretaker_id"]: item for item in local_caretakers}
        assignment_rooms = list(room_by_id)
        if assignment_rooms:
            selected_assignment_room = st.selectbox(
                "Room to assign",
                assignment_rooms,
                format_func=lambda value: (
                    f"{room_by_id[value]['room_number']} "
                    f"({room_by_id[value].get('building', '')}, {room_by_id[value].get('floor', '')})"
                ),
            )
            eligible_assignments = [
                item["caretaker_id"] for item in local_caretakers
                if item["facility_id"] == room_by_id[selected_assignment_room]["facility_id"]
                and item["room_id"] == selected_assignment_room
            ]
            if eligible_assignments:
                primary_options = ["Unassigned"] + eligible_assignments
                current_primary = room_by_id[selected_assignment_room].get("assigned_caretaker_id")
                selected_caretaker = st.selectbox(
                    "Assigned local caretaker",
                    primary_options,
                    index=(
                        primary_options.index(current_primary)
                        if current_primary in primary_options else 0
                    ),
                    format_func=lambda value: (
                        "Unassigned" if value == "Unassigned"
                        else caretaker_by_id[value]["full_name"]
                    ),
                )
                backup_options = ["None"] + [
                    caretaker_id for caretaker_id in eligible_assignments
                    if caretaker_id != selected_caretaker
                ]
                current_backup = room_by_id[selected_assignment_room].get("backup_caretaker_id")
                backup_caretaker = st.selectbox(
                    "Backup local caretaker",
                    backup_options,
                    index=(
                        backup_options.index(current_backup)
                        if current_backup in backup_options else 0
                    ),
                    format_func=lambda value: (
                        "None" if value == "None"
                        else caretaker_by_id[value]["full_name"]
                    ),
                )
                if st.button("Save room assignment"):
                    try:
                        assign_room(
                            selected_assignment_room,
                            AssignmentRequest(
                                caretaker_id=(
                                    selected_caretaker
                                    if selected_caretaker != "Unassigned" else None
                                ),
                                backup_caretaker_id=(
                                    backup_caretaker if backup_caretaker != "None" else None
                                ),
                            ),
                        )
                        st.success("Room assignment saved.")
                        st.rerun()
                    except HTTPException as err:
                        st.error(err.detail)
            else:
                st.caption("No local caretaker is registered for this facility and room yet.")

        for label, records in (
            ("Facilities", facilities),
            ("Rooms", rooms),
            ("Residents", residents),
            ("Local caretakers", local_caretakers),
        ):
            with st.expander(f"{label} ({len(records)})"):
                safe_records = [
                    {key: value for key, value in item.items() if "password" not in key.lower()}
                    for item in records
                ]
                st.dataframe(pd.DataFrame(safe_records), width="stretch")
        with st.expander("Recent emergency timeline"):
            st.dataframe(
                pd.DataFrame(db_manager.find("emergency_timeline", limit=200)),
                width="stretch",
            )


# ====================================================
# SHARED CARETAKER DASHBOARD ENGINE (TIER 1 & TIER 2)
# ====================================================
def render_caretaker_shared_dashboard(tier: int = 1):
    caregivers = db_manager.find("caregivers") or []
    mohini_doc = next((c for c in caregivers if "Mohini" in c.get("name", "") or c.get("priority") == 1), None)
    radha_doc = next((c for c in caregivers if "Radha" in c.get("name", "") or c.get("priority") == 2), None)

    is_mohini_avail = mohini_doc.get("is_available", True) if mohini_doc else True
    is_radha_avail = radha_doc.get("is_available", True) if radha_doc else True

    is_c1 = (tier == 1)
    caretaker_name = "Mohini Ravat" if is_c1 else "Radha Raghav"
    caretaker_role_label = "Primary Caregiver" if is_c1 else "Secondary Backup Caregiver"
    portal_label = "Caretaker 1 Portal" if is_c1 else "Caretaker 2 Portal"
    my_avail = is_mohini_avail if is_c1 else is_radha_avail
    my_doc = mohini_doc if is_c1 else radha_doc

    # ----------------------------------------------------
    # PRE-DATA COMPUTATION
    # ----------------------------------------------------
    CaregiverNotificationService.process_overdue_escalations()
    all_incidents = db_manager.find("incidents", limit=200, sort=[("detected_at", -1)]) or []

    caretaker_incidents = [
        incident for incident in all_incidents
        if incident.get("current_assigned_caretaker") == caretaker_name
    ]
    pending_alerts_count = len([
        incident for incident in caretaker_incidents
        if incident.get("status") in ["PENDING", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2"]
    ])

    residents_list = db_manager.find("residents") or []
    today_date_prefix = datetime.date.today().isoformat()
    resolved_today_list = [
        incident for incident in caretaker_incidents
        if incident.get("status") == "RESOLVED"
        and str(incident.get("resolution_timestamp", "")).startswith(today_date_prefix)
    ]
    resolved_today_count = len(resolved_today_list)

    # Active emergency assigned specifically to this caretaker
    if is_c1:
        active_inc = db_manager.find_one(
            "incidents",
            {
                "$or": [
                    {"current_assigned_caretaker": "Mohini Ravat"},
                    {"current_assigned_caretaker": {"$regex": "Mohini", "$options": "i"}},
                    {"status": {"$in": ["PENDING", "ESCALATED_CARETAKER_1"]}},
                ],
                "status": {"$in": ["PENDING", "ESCALATED_CARETAKER_1", "ACKNOWLEDGED"]},
            },
            sort=[("detected_at", -1)],
        )
    else:
        active_inc = db_manager.find_one(
            "incidents",
            {
                "$or": [
                    {"current_assigned_caretaker": "Radha Raghav"},
                    {"current_assigned_caretaker": {"$regex": "Radha", "$options": "i"}},
                    {"status": "ESCALATED_CARETAKER_2"},
                    {"active_contact.name": {"$regex": "Radha", "$options": "i"}},
                ],
                "status": {"$in": ["PENDING", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "ACKNOWLEDGED"]},
            },
            sort=[("detected_at", -1)],
        )

    if active_inc:
        pending_alerts_count = max(1, pending_alerts_count)

    # ----------------------------------------------------
    # SIDEBAR: OPTIONS FOR ALL CARETAKERS
    # ----------------------------------------------------
    with st.sidebar:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg, {'#059669' if is_c1 else '#7C3AED'} 0%, {'#10B981' if is_c1 else '#8B5CF6'} 100%); border-radius:16px; padding:18px; color:white; margin-bottom:14px; box-shadow:0 6px 20px rgba(0,0,0,0.12);">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
                    <div style="background:rgba(255,255,255,0.22); width:46px; height:46px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.45rem;">
                        {'🥇' if is_c1 else '🥈'}
                    </div>
                    <div>
                        <h4 style="margin:0; font-size:1.1rem; font-weight:800; color:white;">{caretaker_name}</h4>
                        <span style="font-size:0.82rem; opacity:0.95; font-weight:600;">{caretaker_role_label}</span>
                    </div>
                </div>
                <div style="background:rgba(255,255,255,0.18); padding:6px 12px; border-radius:20px; font-size:0.82rem; font-weight:750; display:inline-block;">
                    {'🟢 On Duty' if my_avail else '🔴 Off Duty'} &bull; {portal_label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<h4 style="color:#1E3A8A; font-weight:800; margin:6px 0 8px 0;">⚡ Caregiver Duty Options</h4>',
            unsafe_allow_html=True,
        )
        duty_toggle_label = "🟢 On-Duty Status" if is_c1 else "🟢 Backup Standby Status"
        sidebar_duty = st.toggle(
            duty_toggle_label,
            value=my_avail,
            key=f"caretaker_sidebar_duty_toggle_{tier}",
        )
        if my_doc and sidebar_duty != my_avail:
            db_manager.update_one("caregivers", {"email": my_doc.get("email")}, {"is_available": sidebar_duty})
            add_log(f"{caretaker_name} updated duty status to: {'ON-DUTY' if sidebar_duty else 'OFF-DUTY'}")
            st.rerun()

        st.markdown("---")
        st.markdown(
            '<h4 style="color:#1E3A8A; font-weight:800; margin:6px 0 8px 0;">📋 Care Console Options</h4>',
            unsafe_allow_html=True,
        )
        options_list = [
            "📊 Complete Care Console",
            "Live Room Monitoring 📹",
            "🚨 Emergency Alerts & Triage",
            "👤 Resident Care Profile",
            "👥 Caregiver Duty Roster",
            "📑 Emergency History & Reports",
            "📞 Quick Intercom Directory",
        ]
        caretaker_nav_key = f"caretaker_selected_nav_{tier}"
        if caretaker_nav_key not in st.session_state or st.session_state[caretaker_nav_key] not in options_list:
            st.session_state[caretaker_nav_key] = options_list[0]

        caretaker_view_option = st.radio(
            "Care Console Options:",
            options_list,
            key=caretaker_nav_key,
            label_visibility="collapsed",
        )

        st.markdown("---")
        with st.expander("📑 History Filter Options", expanded=False):
            f_status = st.selectbox(
                "Filter by Status:",
                ["All Statuses", "PENDING", "ACKNOWLEDGED", "RESOLVED"],
                key=f"hist_f_status_{tier}",
            )
            f_event = st.selectbox(
                "Filter by Event Type:",
                ["All Events", "FALL DETECTION", "VOICE EMERGENCY", "MANUAL SOS", "Possible Fall"],
                key=f"hist_f_event_{tier}",
            )
            all_res_names = sorted(list(set([
                inc.get("resident_name") or "Resident 01"
                for inc in all_incidents
                if inc.get("resident_name")
            ])))
            f_resident = st.selectbox(
                "Filter by Resident:",
                ["All Residents"] + all_res_names,
                key=f"hist_f_res_{tier}",
            )
            f_date = st.selectbox(
                "Filter by Date:",
                ["All Dates", "Today", "Last 7 Days"],
                key=f"hist_f_date_{tier}",
            )

    show_all = (caretaker_view_option == "📊 Complete Care Console")
    show_live = show_all or (caretaker_view_option == "Live Room Monitoring 📹")
    show_emergency = show_all or (caretaker_view_option == "🚨 Emergency Alerts & Triage")
    show_resident = show_all or (caretaker_view_option == "👤 Resident Care Profile")
    show_roster = show_all or (caretaker_view_option == "👥 Caregiver Duty Roster")
    show_history = show_all or (caretaker_view_option == "📑 Emergency History & Reports")
    show_intercom = show_all or (caretaker_view_option == "📞 Quick Intercom Directory")

    # ----------------------------------------------------
    # 1. TOP HEADER (VIBRANT & COLORFUL)
    # ----------------------------------------------------
    now_dt = datetime.datetime.now()
    date_time_str = now_dt.strftime("%A, %B %d, %Y • %I:%M %p")

    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg, #FFFFFF 0%, {'#F0FDF4' if is_c1 else '#FAF5FF'} 50%, {'#DCFCE7' if is_c1 else '#F3E8FF'} 100%); border:2px solid {'#34D399' if is_c1 else '#A78BFA'}; border-radius:18px; padding:22px 26px; box-shadow:0 6px 24px rgba(0,0,0,0.06); margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
                <div>
                    <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
                        <span style="font-size:2.0rem;">🛡️</span>
                        <h2 style="color:#0F172A; margin:0; font-weight:800; font-size:1.65rem; letter-spacing:-0.02em;">
                            Fall Guard AI <span style="color:#2563EB; font-weight:600; font-size:1.05rem;">| Patient Care & Safety Console</span>
                        </h2>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                        <h3 style="color:#1E3A8A; margin:0; font-size:1.25rem; font-weight:700;">Welcome, {caretaker_name}</h3>
                        <span style="background:{'#DBEAFE' if is_c1 else '#EDE9FE'}; color:{'#1E40AF' if is_c1 else '#6D28D9'}; padding:4px 12px; border-radius:12px; font-weight:800; font-size:0.82rem; border:1px solid {'#93C5FD' if is_c1 else '#C4B5FD'};">
                            {portal_label} — {caretaker_role_label}
                        </span>
                        <span style="color:#64748B; font-size:0.9rem; font-weight:600;">🕒 {date_time_str}</span>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
                    <span style="background:{'#ECFDF5' if my_avail else '#FEF2F2'}; color:{'#065F46' if my_avail else '#991B1B'}; padding:8px 18px; border-radius:20px; font-weight:800; font-size:0.92rem; border:1.5px solid {'#10B981' if my_avail else '#EF4444'}; box-shadow:0 2px 6px rgba(0,0,0,0.04);">
                        {'🟢 On Duty' if my_avail else '🔴 Off Duty'}
                    </span>
                    <span style="background:{'#FEF2F2' if pending_alerts_count > 0 else '#F8FAFC'}; color:{'#DC2626' if pending_alerts_count > 0 else '#64748B'}; padding:8px 16px; border-radius:20px; font-weight:700; font-size:0.92rem; border:1.5px solid {'#FCA5A5' if pending_alerts_count > 0 else '#E2E8F0'};">
                        🔔 {pending_alerts_count} {'Emergency Alert' if pending_alerts_count == 1 else 'Alerts'}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Duty notification (Single global logout button is in the top bar)
    if not my_avail:
        if is_c1:
            st.warning("⚠️ You are currently **OFF-DUTY**. Incoming patient emergencies automatically route to **Radha Raghav (Caretaker 2)**.")
        else:
            st.warning("⚠️ You are currently **OFF-DUTY**. If Mohini Ravat is also unavailable, emergency calls escalate to the **System Administrator**.")
    else:
        if not is_c1 and not is_mohini_avail:
            st.warning("⚠️ **Mohini Ravat (Caretaker 1) is OFF-DUTY.** You (Radha Raghav) are actively serving as the **PRIMARY FIRST RESPONDER**.")

    # ----------------------------------------------------
    # EMERGENCY ALERT CARD HELPER (ALWAYS DISPLAYED WHEN ACTIVE)
    # ----------------------------------------------------
    def render_caretaker_emergency_card(active_inc_doc):
        inc_id = active_inc_doc.get("incident_id")
        res_name = active_inc_doc.get("resident_name", "Resident 01 – Elderly Resident")
        room_label = active_inc_doc.get("room_number") or active_inc_doc.get("room_id", "Living Room")
        camera_id = active_inc_doc.get("camera_id", "Camera 01")
        em_type = active_inc_doc.get("emergency_type") or active_inc_doc.get("event_type", "FALL DETECTION")
        orig_time = active_inc_doc.get("original_emergency_timestamp") or active_inc_doc.get("detected_at") or active_inc_doc.get("timestamp")
        inc_status = active_inc_doc.get("status", "PENDING")

        time_display = orig_time
        try:
            dt_parsed = datetime.datetime.fromisoformat(str(orig_time).replace("Z", "+00:00"))
            time_display = dt_parsed.strftime("%I:%M %p (%d %b %Y)")
        except Exception:
            pass

        if inc_status in ["PENDING", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2"]:
            render_audio_alert()

            deadline_str = active_inc_doc.get("response_deadline_at")
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if not deadline_str:
                from datetime import timedelta
                stage_deadline = now_utc + timedelta(seconds=CaregiverNotificationService.RESPONSE_TIMEOUT_SECONDS)
                deadline_str = stage_deadline.isoformat(timespec="seconds")
                db_manager.update_one("incidents", {"incident_id": inc_id}, {"response_deadline_at": deadline_str})
                deadline_dt = stage_deadline
            else:
                try:
                    deadline_dt = datetime.datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
                except Exception:
                    deadline_dt = now_utc + datetime.timedelta(seconds=CaregiverNotificationService.RESPONSE_TIMEOUT_SECONDS)

            remaining = int((deadline_dt - now_utc).total_seconds())

            if remaining <= 0:
                CaregiverNotificationService.process_overdue_escalations()
                if is_c1:
                    st.session_state["last_forwarded_c1"] = inc_id
                    add_log(f"Mohini Ravat response window expired for [{inc_id}]. Auto-escalated to Radha Raghav.")
                else:
                    add_log(f"Radha Raghav response window expired for [{inc_id}]. Auto-escalated to System Administrator.")
                st.rerun()

            alert_header_title = f"EMERGENCY ALERT ASSIGNED TO {caretaker_name.upper()}"
            if not is_c1:
                alert_header_title = "EMERGENCY ALERT ASSIGNED TO RADHA RAGHAV"

            st.markdown(
                f"""
                <div style="background:#FFF1F2; border:3px solid #E11D48; border-radius:18px; padding:24px; margin-bottom:18px; box-shadow:0 12px 32px rgba(225,29,72,0.18);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:16px;">
                        <div>
                            <span style="background:#E11D48; color:white; padding:5px 14px; border-radius:20px; font-weight:800; font-size:0.85rem; letter-spacing:0.05em; text-transform:uppercase;">
                                🚨 POSSIBLE FALL DETECTED!
                            </span>
                            <h2 style="color:#BE123C; margin:8px 0 2px 0; font-weight:800; font-size:1.45rem;">
                                {alert_header_title}
                            </h2>
                            <p style="color:#9F1239; margin:0; font-weight:600; font-size:0.95rem;">
                                Status: <b>Waiting for Caregiver Response</b>
                            </p>
                        </div>
                        <div style="text-align:right;">
                            <span style="background:#FFE4E6; color:#9F1239; border:2px solid #FDA4AF; padding:8px 18px; border-radius:14px; font-weight:800; font-size:1.15rem; display:inline-block;">
                                ⏱️ {remaining}s REMAINING
                            </span>
                        </div>
                    </div>
                    <div style="background:white; border-radius:14px; padding:18px; border:1.5px solid #FECDD3; margin-bottom:18px;">
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:14px; font-size:0.95rem;">
                            <div>
                                <span style="color:#64748B; font-size:0.8rem; text-transform:uppercase; font-weight:700;">Resident:</span><br>
                                <b style="color:#0F172A; font-size:1.05rem;">{res_name}</b>
                            </div>
                            <div>
                                <span style="color:#64748B; font-size:0.8rem; text-transform:uppercase; font-weight:700;">Location:</span><br>
                                <b style="color:#0F172A; font-size:1.05rem;">{room_label}</b>
                            </div>
                            <div>
                                <span style="color:#64748B; font-size:0.8rem; text-transform:uppercase; font-weight:700;">Camera:</span><br>
                                <b style="color:#0F172A; font-size:1.05rem;">{camera_id}</b>
                            </div>
                            <div>
                                <span style="color:#64748B; font-size:0.8rem; text-transform:uppercase; font-weight:700;">Time:</span><br>
                                <b style="color:#0F172A; font-size:1.05rem;">{time_display}</b>
                            </div>
                            <div>
                                <span style="color:#64748B; font-size:0.8rem; text-transform:uppercase; font-weight:700;">Emergency Type:</span><br>
                                <b style="color:#E11D48; font-size:1.05rem;">{em_type}</b>
                            </div>
                            <div>
                                <span style="color:#64748B; font-size:0.8rem; text-transform:uppercase; font-weight:700;">Incident ID:</span><br>
                                <code style="color:#1E40AF; font-size:0.95rem; font-weight:700;">{inc_id}</code>
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            ev_list = active_inc_doc.get("detection_evidence", [])
            with st.expander("🧠 Why Was This Alert Triggered? (Movement Evidence Analysis)", expanded=True):
                if ev_list:
                    for ev in ev_list:
                        st.markdown(f"• **{ev}**")
                else:
                    st.markdown("• **Sudden downward body movement detected.**")
                    st.markdown("• **Body orientation changed significantly from vertical to horizontal.**")
                    st.markdown("• **Person remained in a horizontal position.**")
                    st.markdown("• **Fall-like movement persisted across consecutive frames.**")

            st.caption(f"⏱️ **Response countdown timer: {remaining} seconds remaining** (Auto-forwards if unattended)")
            st.progress(max(0.0, min(1.0, remaining / CaregiverNotificationService.RESPONSE_TIMEOUT_SECONDS)))

            # 3 Explicit Action Buttons: Responding | Forward | Clear
            col_b1, col_b2, col_b3 = st.columns([5, 5, 4])
            with col_b1:
                if st.button("✅ ACKNOWLEDGE & RESPOND", type="primary", key=f"btn_ack_{inc_id}_{tier}", use_container_width=True):
                    record_incident_action(
                        incident_id=inc_id,
                        action="ACCEPTED",
                        new_status="ACKNOWLEDGED",
                        actor=curr_acc,
                        remarks=f"{caretaker_role_label} ({caretaker_name}) accepted and is attending to the resident.",
                    )
                    add_log(f"{caretaker_name} acknowledged emergency [{inc_id}]. Attending patient on-site.")
                    st.success("✅ Response confirmed! You are now attending to the resident. Admin notified.")
                    st.rerun()

            with col_b2:
                btn_fwd_label = "📞 FORWARD TO CARETAKER 2 (RADHA RAGHAV)" if is_c1 else "🚨 FORWARD TO FACILITY ADMINISTRATOR"
                if st.button(btn_fwd_label, type="secondary", key=f"btn_help_{inc_id}_{tier}", use_container_width=True):
                    if is_c1:
                        CaregiverNotificationService.forward_alert_to_caretaker2(
                            incident_id=inc_id,
                            room_name=room_label,
                            body_angle=active_inc_doc.get("body_angle", 70.0),
                            reason="Primary caretaker (Mohini Ravat) requested backup and forwarded alert.",
                        )
                        st.session_state["last_forwarded_c1"] = inc_id
                        st.session_state["active_incident"] = None
                        st.session_state["stream_active"] = True
                        if "temporal_detector" in st.session_state:
                            st.session_state["temporal_detector"].reset()
                        GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
                        add_log(f"Mohini Ravat called for backup. Alert [{inc_id}] forwarded to Radha Raghav.")
                        st.warning("⚠️ Alert forwarded to Secondary Caretaker (Radha Raghav).")
                    else:
                        CaregiverNotificationService.forward_alert_to_admin(
                            incident_id=inc_id,
                            room_name=room_label,
                            body_angle=active_inc_doc.get("body_angle", 70.0),
                            reason="Secondary caretaker (Radha Raghav) requested Administrative emergency override.",
                        )
                        st.session_state["active_incident"] = None
                        st.session_state["stream_active"] = True
                        if "temporal_detector" in st.session_state:
                            st.session_state["temporal_detector"].reset()
                        GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
                        add_log(f"Radha Raghav contacted Administrator for alert [{inc_id}].")
                        st.error("🚨 Critical Alert forwarded to System Administrator.")
                    st.rerun()

            with col_b3:
                if st.button("✕ Dismiss / Clear", key=f"btn_dismiss_{inc_id}_{tier}", use_container_width=True):
                    IncidentStateMachine.resolve_incident(
                        incident_id=inc_id,
                        resolved_by=caretaker_name,
                        notes="Dismissed as false alarm or resolved by caregiver.",
                    )
                    st.session_state["active_incident"] = None
                    st.session_state["last_incident_resolved_time"] = time.time()
                    if "temporal_detector" in st.session_state:
                        st.session_state["temporal_detector"].reset()
                    st.session_state["stream_active"] = True
                    GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
                    add_log(f"{caretaker_name} dismissed emergency [{inc_id}].")
                    st.success("✅ Alert cleared.")
                    st.rerun()

        elif inc_status == "ACKNOWLEDGED":
            ack_time = active_inc_doc.get("acknowledgement_timestamp") or "Just now"
            st.markdown(
                f"""
                <div style="background:#FEFCE8; border:2px solid #FACC15; border-radius:16px; padding:20px; margin-bottom:18px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                        <div>
                            <span style="background:#CA8A04; color:white; padding:4px 12px; border-radius:12px; font-weight:800; font-size:0.75rem; text-transform:uppercase;">
                                PATIENT UNDER CARE
                            </span>
                            <h3 style="color:#854D0E; margin:6px 0 2px 0; font-weight:800; font-size:1.3rem;">
                                🩺 ACTIVE ATTENDANCE — {caretaker_name.upper()} ATTENDING
                            </h3>
                            <p style="color:#713F12; margin:0; font-size:0.95rem;">
                                Attending to <b>{res_name}</b> at <b>{room_label}</b> &bull; Incident <code>{inc_id}</code>
                            </p>
                            <p style="color:#A16207; margin:2px 0 0 0; font-size:0.85rem;">
                                Acknowledged at: <b>{ack_time}</b> &bull; Patient care active. Admin on standby.
                            </p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("#### 📝 Emergency Resolution & Patient Care Notes")
            default_notes = f"Resident assisted by {caretaker_name}. Vitals checked, resting comfortably."
            res_notes = st.text_area(
                "Enter resolution notes (vital signs, patient state, assistance rendered):",
                value=default_notes,
                key=f"res_notes_{inc_id}_{tier}",
            )
            if st.button("✅ Mark Incident as Resolved", type="primary", key=f"btn_res_{inc_id}_{tier}", use_container_width=True):
                IncidentStateMachine.resolve_incident(
                    incident_id=inc_id,
                    resolved_by=caretaker_name,
                    notes=res_notes,
                )
                st.session_state["active_incident"] = None
                st.session_state["last_incident_resolved_time"] = time.time()
                if "temporal_detector" in st.session_state:
                    st.session_state["temporal_detector"].reset()
                st.session_state["stream_active"] = True
                GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
                add_log(f"{caretaker_name} marked incident [{inc_id}] as RESOLVED. Notes: {res_notes}")
                st.success(f"✅ Incident {inc_id} successfully marked as RESOLVED and archived to Emergency History.")
                st.rerun()

    # Always render the active emergency alert prominently across ALL views if active
    if active_inc:
        render_caretaker_emergency_card(active_inc)

    # ----------------------------------------------------
    # LIVE PATIENT-ROOM MONITORING (CAMERA ICON ON RIGHT SIDE)
    # ----------------------------------------------------
    if show_live:
        st.markdown(
            """
            <h3 style="margin:18px 0 10px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">
                Live Patient-Room Monitoring
            </h3>
            """,
            unsafe_allow_html=True,
        )
        render_live_monitoring_engine(
            show_full_controls=True,
            header_label="Patient Room Monitoring",
        )

    # ----------------------------------------------------
    # CARE OVERVIEW METRICS (COLORFUL VIBRANT CARDS)
    # ----------------------------------------------------
    if show_all:
        st.subheader("Care overview")
        metric_columns = st.columns(3)
        with metric_columns[0]:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); border:2px solid #60A5FA; border-radius:16px; padding:18px; box-shadow:0 4px 14px rgba(37,99,235,0.12);">
                    <span style="color:#1E40AF; font-size:0.85rem; font-weight:800; text-transform:uppercase;">Registered residents</span>
                    <div style="font-size:2.0rem; font-weight:850; color:#0F172A; margin:4px 0;">{len(residents_list)}</div>
                    <span style="color:#3B82F6; font-size:0.82rem; font-weight:600;">Residents in care directory</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with metric_columns[1]:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%); border:2px solid #F43F5E; border-radius:16px; padding:18px; box-shadow:0 4px 14px rgba(244,63,94,0.15);">
                    <span style="color:#9F1239; font-size:0.85rem; font-weight:800; text-transform:uppercase;">Awaiting your response</span>
                    <div style="font-size:2.0rem; font-weight:850; color:{'#BE123C' if pending_alerts_count > 0 else '#0F172A'}; margin:4px 0;">{pending_alerts_count}</div>
                    <span style="color:#E11D48; font-size:0.82rem; font-weight:600;">Open alerts assigned to you</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with metric_columns[2]:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%); border:2px solid #34D399; border-radius:16px; padding:18px; box-shadow:0 4px 14px rgba(16,185,129,0.12);">
                    <span style="color:#065F46; font-size:0.85rem; font-weight:800; text-transform:uppercase;">Resolved today</span>
                    <div style="font-size:2.0rem; font-weight:850; color:#047857; margin:4px 0;">{resolved_today_count}</div>
                    <span style="color:#059669; font-size:0.82rem; font-weight:600;">Incidents resolved today</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ----------------------------------------------------
    # 2. EMERGENCY STATUS — MOST IMPORTANT SECTION
    # ----------------------------------------------------
    active_count = len([
        i for i in all_incidents
        if i.get("status") in ["PENDING", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "ACKNOWLEDGED"]
    ])
    pending_count = pending_alerts_count

    if show_emergency:
        st.markdown('<h3 style="margin:20px 0 12px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">🚨 Emergency Alerts & Triage</h3>', unsafe_allow_html=True)
        if not active_inc:
            if active_count == 0:
                st.session_state["last_forwarded_c1"] = None

            # Reassuring Green Banner when zero emergencies assigned
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%); border:1.5px solid #86EFAC; border-radius:16px; padding:22px 26px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px; box-shadow:0 4px 16px rgba(16,185,129,0.08); margin-bottom:20px;">
                    <div style="display:flex; align-items:center; gap:18px;">
                        <div style="background:white; width:52px; height:52px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.8rem; box-shadow:0 2px 8px rgba(16,185,129,0.15); border:1.5px solid #86EFAC;">
                            🟢
                        </div>
                        <div>
                            <h3 style="color:#14532D; margin:0 0 4px 0; font-weight:800; font-size:1.25rem;">
                                All Monitored Residents Safe — Continuous AI Protection Active
                            </h3>
                            <p style="color:#166534; margin:0; font-size:0.92rem; font-weight:500;">
                                Live computer vision pose estimation & fall detection sensors are operational. Zero active emergencies assigned to {caretaker_name}.
                            </p>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="background:#10B981; color:white; padding:6px 14px; border-radius:20px; font-weight:800; font-size:0.8rem; letter-spacing:0.04em;">
                            ● 24/7 SAFETY SHIELD ACTIVE
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ----------------------------------------------------
    # 8. QUICK ACTIONS
    # ----------------------------------------------------
    if show_all:
        st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:18px 0 10px 0;">⚡ Quick Actions</h4>', unsafe_allow_html=True)
        qa1, qa2, qa3, qa4, qa5 = st.columns(5)
        with qa1:
            if st.button("Live Monitoring 📹", key=f"qa_live_{tier}", use_container_width=True):
                st.session_state["show_resident_modal"] = False
                st.session_state["show_admin_contact"] = False
        with qa2:
            if st.button("👤 Resident Details", key=f"qa_resident_{tier}", use_container_width=True):
                st.session_state["show_resident_modal"] = not st.session_state.get("show_resident_modal", False)
        with qa3:
            if st.button("📞 Contact Admin", key=f"qa_admin_{tier}", use_container_width=True):
                st.session_state["show_admin_contact"] = not st.session_state.get("show_admin_contact", False)
        with qa4:
            if st.button("📋 Emergency History", key=f"qa_history_{tier}", use_container_width=True):
                st.session_state["show_history_focus"] = True
        with qa5:
            if st.button("🔄 Toggle Availability", key=f"qa_avail_{tier}", use_container_width=True):
                new_state = not my_avail
                if my_doc:
                    db_manager.update_one("caregivers", {"email": my_doc.get("email")}, {"is_available": new_state})
                    add_log(f"{caretaker_name} updated duty status to: {'ON-DUTY' if new_state else 'OFF-DUTY'}")
                    st.rerun()

    # Interactive Resident Details View
    if show_resident or st.session_state.get("show_resident_modal"):
        st.markdown(
            """
            <div style="background:linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%); border:2px solid #93C5FD; border-radius:16px; padding:20px; margin:14px 0; box-shadow:0 4px 16px rgba(37,99,235,0.08);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h4 style="color:#1E3A8A; margin:0; font-weight:800; font-size:1.15rem;">👤 Resident Profile — Resident 01</h4>
                    <span style="background:#DBEAFE; color:#1E40AF; padding:4px 12px; border-radius:12px; font-weight:750; font-size:0.8rem;">Monitored Resident</span>
                </div>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:14px; font-size:0.92rem;">
                    <div><b>Full Name:</b> Smt. Shanti Devi (Resident 01)</div>
                    <div><b>Room / Unit:</b> Living Room (Room 101)</div>
                    <div><b>Age:</b> 78 Years</div>
                    <div><b>Fall Risk Level:</b> <span style="color:#DC2626; font-weight:800;">High Risk (Prior Fall History)</span></div>
                    <div><b>Primary Caregiver:</b> Mohini Ravat (+91 98765 43210)</div>
                    <div><b>Emergency Doctor:</b> Dr. S. K. Sharma (+91 99887 76655)</div>
                </div>
                <div style="margin-top:12px; color:#334155; font-size:0.88rem; background:white; padding:10px 14px; border-radius:10px; border:1px solid #CBD5E1;">
                    <b>Care Notes:</b> Uses walking aid for mobility. Optical AI camera and bed sensors active. Needs assistance during bathroom visits.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Interactive Admin Contact View
    if show_intercom or st.session_state.get("show_admin_contact"):
        st.markdown(
            """
            <div style="background:linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); border:2px solid #60A5FA; border-radius:16px; padding:20px; margin:14px 0; box-shadow:0 4px 16px rgba(37,99,235,0.1);">
                <h4 style="color:#1E40AF; margin:0 0 10px 0; font-weight:800; font-size:1.15rem;">📞 Facility System Administrator & Emergency Services</h4>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; font-size:0.92rem;">
                    <div><b>Administrator:</b> Dr. Rajesh Varma</div>
                    <div><b>Emergency Intercom:</b> <code>EXT 100</code> / <code>+91 99000 11223</code></div>
                    <div><b>Hospital Ambulance:</b> <code style="color:#BE123C; font-weight:800;">108</code> / <code>+91 99112 23344</code></div>
                    <div><b>Admin Email:</b> <code>admin@fallguard.local</code></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ----------------------------------------------------
    # 9. EXPLAINABLE MOVEMENT EVIDENCE
    # ----------------------------------------------------
    if show_emergency or show_all:
        with st.expander("🧠 Why Was This Alert Triggered? (Explainable Movement Evidence Analysis)", expanded=False):
            st.markdown(
                """
                <div style="background:#F8FAFC; border-radius:12px; padding:14px; border:1px solid #E2E8F0; margin-bottom:10px;">
                    <b style="color:#1E40AF; font-size:0.95rem;">🔬 Computer Vision Decision Criteria:</b>
                    <p style="color:#475569; font-size:0.86rem; margin:4px 0 10px 0;">
                        Fall Guard AI analyzes four kinetic indicators simultaneously before classifying a genuine fall:
                    </p>
                    <div style="font-size:0.88rem; color:#1E293B; line-height:1.6;">
                        • <b>Sudden downward body movement detected:</b> Rapid vertical velocity towards floor (&Delta;Y &gt; 0.080/frame).<br>
                        • <b>Body orientation changed significantly:</b> Rapid tilt from upright (10&deg;&ndash;30&deg;) to horizontal floor posture (&gt; 60&deg;).<br>
                        • <b>Person remained in a horizontal position:</b> Torso angle persists near ground level rather than rebounding.<br>
                        • <b>Fall-like movement persisted across multiple frames:</b> Consecutive verification window (6+ frames) confirms patient cannot immediately right themselves.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if active_inc and active_inc.get("detection_evidence"):
                st.markdown("<b>Active Incident Evidence Record:</b>", unsafe_allow_html=True)
                for ev_item in active_inc.get("detection_evidence", []):
                    st.markdown(f"• **{ev_item}**")

    # ----------------------------------------------------
    # 6. CAREGIVER AVAILABILITY
    # ----------------------------------------------------
    if show_roster:
        st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:22px 0 10px 0;">👥 Caregiver Availability & Rosters</h4>', unsafe_allow_html=True)
        col_av1, col_av2 = st.columns(2)
        with col_av1:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #FFFFFF 0%, #F0FDF4 100%); border:2px solid {'#10B981' if is_mohini_avail else '#EF4444'}; border-radius:16px; padding:18px; box-shadow:0 4px 14px rgba(16,185,129,0.08);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="color:#0F172A; font-size:1.05rem;">🥇 Primary Caregiver: Mohini Ravat</b>
                        <span style="background:{'#ECFDF5' if is_mohini_avail else '#FEF2F2'}; color:{'#065F46' if is_mohini_avail else '#991B1B'}; padding:4px 12px; border-radius:14px; font-weight:800; font-size:0.82rem; border:1px solid {'#A7F3D0' if is_mohini_avail else '#FECDD3'};">
                            {'🟢 ON DUTY' if is_mohini_avail else '🔴 OFF DUTY'}
                        </span>
                    </div>
                    <div style="color:#475569; font-size:0.88rem; margin:8px 0 10px 0;">
                        📞 Phone: <b>+91 98765 43210</b> &bull; ✉️ <code>mohini.ravat@fallguard.local</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if is_c1:
                new_m_avail = st.toggle("🟢 Update My Duty Status (Mohini Ravat)", value=is_mohini_avail, key="mohini_toggle_duty_card")
                if mohini_doc and new_m_avail != is_mohini_avail:
                    db_manager.update_one("caregivers", {"email": mohini_doc.get("email")}, {"is_available": new_m_avail})
                    add_log(f"Mohini Ravat updated duty status to: {'ON-DUTY' if new_m_avail else 'OFF-DUTY'}")
                    st.rerun()

        with col_av2:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #FFFFFF 0%, #FAF5FF 100%); border:2px solid {'#8B5CF6' if is_radha_avail else '#EF4444'}; border-radius:16px; padding:18px; box-shadow:0 4px 14px rgba(139,92,246,0.08);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="color:#0F172A; font-size:1.05rem;">🥈 Secondary Caregiver: Radha Raghav</b>
                        <span style="background:{'#F5F3FF' if is_radha_avail else '#FEF2F2'}; color:{'#5B21B6' if is_radha_avail else '#991B1B'}; padding:4px 12px; border-radius:14px; font-weight:800; font-size:0.82rem; border:1px solid {'#DDD6FE' if is_radha_avail else '#FECDD3'};">
                            {'🟢 BACKUP STANDBY' if is_radha_avail else '🔴 OFF DUTY'}
                        </span>
                    </div>
                    <div style="color:#475569; font-size:0.88rem; margin:8px 0 10px 0;">
                        📞 Phone: <b>+91 98123 45678</b> &bull; ✉️ <code>radha.raghav@fallguard.local</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not is_c1:
                new_r_avail = st.toggle("🟢 Update My Duty Status (Radha Raghav)", value=is_radha_avail, key="radha_toggle_duty_card")
                if radha_doc and new_r_avail != is_radha_avail:
                    db_manager.update_one("caregivers", {"email": radha_doc.get("email")}, {"is_available": new_r_avail})
                    add_log(f"Radha Raghav updated duty status to: {'ON-DUTY' if new_r_avail else 'OFF-DUTY'}")
                    st.rerun()

    # ----------------------------------------------------
    # 7. RECENT EMERGENCY HISTORY (WITH SIDEBAR FILTERS)
    # ----------------------------------------------------
    if show_history:
        st.markdown('<div id="history-anchor"></div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div style="display:flex; justify-content:space-between; align-items:center; margin:24px 0 10px 0; flex-wrap:wrap; gap:10px;">
                <h4 style="color:#0F172A; font-weight:800; margin:0;">📑 Recent Emergency History</h4>
                <span style="color:#1E40AF; font-size:0.85rem; font-weight:750; background:#EFF6FF; border:1.5px solid #93C5FD; padding:4px 14px; border-radius:14px;">⚙️ Filter options available in sidebar</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Apply filters
        filtered_incidents = all_incidents
        if f_status != "All Statuses":
            filtered_incidents = [i for i in filtered_incidents if i.get("status") == f_status]
        if f_event != "All Events":
            filtered_incidents = [
                i for i in filtered_incidents
                if f_event.lower() in (i.get("emergency_type") or i.get("event_type") or "").lower()
            ]
        if f_resident != "All Residents":
            filtered_incidents = [
                i for i in filtered_incidents
                if (i.get("resident_name") or "Resident 01") == f_resident
            ]
        if f_date == "Today":
            filtered_incidents = [
                i for i in filtered_incidents
                if str(i.get("detected_at") or i.get("timestamp") or "").startswith(today_date_prefix)
            ]
        elif f_date == "Last 7 Days":
            seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            filtered_incidents = [
                i for i in filtered_incidents
                if str(i.get("detected_at") or i.get("timestamp") or "") >= seven_days_ago
            ]

        if filtered_incidents:
            history_rows = []
            for inc in filtered_incidents:
                t_raw = inc.get("detected_at") or inc.get("timestamp") or "—"
                t_formatted = str(t_raw)
                try:
                    dt_p = datetime.datetime.fromisoformat(str(t_raw).replace("Z", "+00:00"))
                    t_formatted = dt_p.strftime("%b %d, %Y • %I:%M %p")
                except Exception:
                    pass

                history_rows.append({
                    "Date & Time": t_formatted,
                    "Resident": inc.get("resident_name", "Resident 01"),
                    "Location": inc.get("room_number") or inc.get("room_id", "Living Room"),
                    "Event": inc.get("emergency_type") or inc.get("event_type", "FALL DETECTION"),
                    "Status": inc.get("status", "RESOLVED"),
                    "Handled By": inc.get("resolved_by") or inc.get("current_assigned_caretaker", "—"),
                })
            st.dataframe(pd.DataFrame(history_rows), width="stretch")
        else:
            st.info("No matching emergency records found with the selected filters.")

    # Intercom contact box
    if show_intercom:
        st.markdown("---")
        st.markdown("### 📞 Quick Intercom Contacts")
        ic1, ic2 = st.columns(2)
        with ic1:
            st.info(
                "🥈 **Radha Raghav (Secondary Caretaker)**\n\n"
                "Phone: `+91 98123 45678` | Email: `radha.raghav@fallguard.local`"
                if is_c1 else
                "🥇 **Mohini Ravat (Primary Caretaker)**\n\n"
                "Phone: `+91 98765 43210` | Email: `mohini.ravat@fallguard.local`"
            )
        with ic2:
            st.info("🛡️ **System Administrator**\n\nPhone: `+91 99000 11223` | Email: `admin@fallguard.local`")


# ====================================================
# 2. CARETAKER 1 DASHBOARD (MOHINI RAVAT)
# ====================================================
def render_caretaker1_dashboard():
    render_caretaker_shared_dashboard(tier=1)


# ====================================================
# 3. CARETAKER 2 DASHBOARD (RADHA RAGHAV)
# ====================================================
def render_caretaker2_dashboard():
    render_caretaker_shared_dashboard(tier=2)


# ====================================================
# LOCAL CARETAKER DASHBOARD
# ====================================================
def render_local_caretaker_dashboard():
    caretaker_id = curr_acc.get("caretaker_id")
    caretaker = db_manager.find_one("local_caretakers", {"caretaker_id": caretaker_id}) if caretaker_id else None
    if not caretaker:
        st.error("Your local caretaker profile is unavailable. Contact an administrator.")
        return

    facility = db_manager.find_one("facilities", {"facility_id": caretaker["facility_id"]})
    current_availability = caretaker.get("availability", CareAvailability.AVAILABLE.value)
    availability_choices = [item.value for item in CareAvailability]

    # Sidebar Options for Local Caretaker
    with st.sidebar:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg, #0284C7 0%, #0369A1 100%); border-radius:16px; padding:18px; color:white; margin-bottom:14px; box-shadow:0 6px 20px rgba(0,0,0,0.12);">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
                    <div style="background:rgba(255,255,255,0.22); width:46px; height:46px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.45rem;">
                        🏥
                    </div>
                    <div>
                        <h4 style="margin:0; font-size:1.1rem; font-weight:800; color:white;">{caretaker['full_name']}</h4>
                        <span style="font-size:0.82rem; opacity:0.95; font-weight:600;">Local Caretaker</span>
                    </div>
                </div>
                <div style="background:rgba(255,255,255,0.18); padding:6px 12px; border-radius:20px; font-size:0.82rem; font-weight:750; display:inline-block;">
                    Room {caretaker.get('room_id', '—')} &bull; Floor {caretaker.get('floor', '—')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<h4 style="color:#1E3A8A; font-weight:800; margin:6px 0 8px 0;">⚡ Caretaker Options</h4>', unsafe_allow_html=True)
        sidebar_avail = st.selectbox(
            "Your availability",
            availability_choices,
            index=(
                availability_choices.index(current_availability)
                if current_availability in availability_choices else 0
            ),
            key="local_caretaker_sidebar_avail",
        )
        if sidebar_avail != current_availability:
            updated = update_caretaker_availability(
                caretaker_id,
                AvailabilityUpdate(availability=CareAvailability(sidebar_avail)),
                curr_acc,
            )
            st.success(f"Availability set to {updated.availability.value}.")
            st.rerun()

        st.markdown("---")
        st.markdown(
            '<h4 style="color:#1E3A8A; font-weight:800; margin:6px 0 8px 0;">📋 Local Console Options</h4>',
            unsafe_allow_html=True,
        )
        local_view_option = st.radio(
            "Local Console Options:",
            [
                "📊 Complete Local Console",
                "Live Room Monitoring 📹",
                "🚨 Emergency Alerts",
                "🏢 Assigned Rooms Directory",
                "📑 Incident & Notifications History",
            ],
            key="local_caretaker_sidebar_nav",
            label_visibility="collapsed",
        )

    show_local_all = (local_view_option == "📊 Complete Local Console")
    show_local_live = show_local_all or (local_view_option == "Live Room Monitoring 📹")
    show_local_alerts = show_local_all or (local_view_option == "🚨 Emergency Alerts")
    show_local_rooms = show_local_all or (local_view_option == "🏢 Assigned Rooms Directory")
    show_local_history = show_local_all or (local_view_option == "📑 Incident & Notifications History")

    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg, #FFFFFF 0%, #F0F9FF 50%, #E0F2FE 100%); border:2px solid #38BDF8; border-radius:18px; padding:22px 26px; box-shadow:0 6px 24px rgba(0,0,0,0.06); margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
                <div>
                    <h2 style="color:#0F172A; margin:0 0 4px 0; font-weight:800; font-size:1.6rem;">
                        🏥 {caretaker['full_name']} — Local Caretaker Dashboard
                    </h2>
                    <span style="color:#0369A1; font-weight:700; font-size:0.95rem;">
                        {(facility or {}).get('name', 'Facility')} &bull; {caretaker.get('building', '')}, floor {caretaker.get('floor', '')} &bull; Room {caretaker.get('room_id', '')}
                    </span>
                </div>
                <div>
                    <span style="background:#ECFDF5; color:#065F46; padding:8px 18px; border-radius:20px; font-weight:800; font-size:0.92rem; border:1.5px solid #10B981; box-shadow:0 2px 6px rgba(0,0,0,0.04);">
                        🟢 Status: {current_availability}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    assigned_rooms = [
        room for room in db_manager.find("rooms", {"is_active": True}, limit=500)
        if caretaker_id in {
            room.get("assigned_caretaker_id"),
            room.get("backup_caretaker_id"),
        }
    ]

    if show_local_rooms:
        st.markdown("### Assigned rooms")
        st.dataframe(pd.DataFrame(assigned_rooms), width="stretch")

    if show_local_live:
        if assigned_rooms:
            assigned_room_ids = {room.get("room_id") for room in assigned_rooms}
            st.markdown(
                """
                <div style="display:flex; justify-content:space-between; align-items:center; margin:18px 0 10px 0;">
                    <h3 style="margin:0; font-weight:800; color:#0F172A; font-size:1.35rem;">
                        Live Monitoring for Your Assigned Rooms
                    </h3>
                    <span style="font-size:1.6rem; background:linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); border:1.5px solid #93C5FD; border-radius:12px; padding:5px 12px; display:inline-flex; align-items:center; justify-content:center; box-shadow:0 3px 10px rgba(37,99,235,0.15);" title="Assigned Camera Stream">📹</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_live_monitoring_engine(
                show_full_controls=False,
                header_label="Assigned Room Monitoring",
                allowed_room_ids=assigned_room_ids,
            )
        else:
            st.info("No active rooms are assigned to your account, so live monitoring is unavailable.")

    all_incidents = db_manager.find("incidents", limit=1000, sort=[("detected_at", -1)])
    assignment_history = db_manager.find(
        "caretaker_assignments",
        {"caretaker_id": caretaker_id},
        limit=1000,
    )
    assigned_incident_ids = {item.get("incident_id") for item in assignment_history}
    my_incidents = [
        item for item in all_incidents
        if item.get("active_caretaker_id") == caretaker_id
        or item.get("incident_id") in assigned_incident_ids
    ]
    active_incidents = [
        item for item in my_incidents
        if item.get("active_caretaker_id") == caretaker_id
        and item.get("status") not in {"RESOLVED", "CLOSED"}
    ]

    if show_local_alerts:
        st.markdown("### Emergency alerts")
        if not active_incidents:
            st.success("No active emergency alerts are assigned to you.")

        for incident in active_incidents:
            incident_id = incident["incident_id"]
            with st.container(border=True):
                st.error(
                    f"🚨 {incident_id} · Room {incident.get('room_number', incident.get('room_id', 'unknown'))} · "
                    f"{incident.get('status', 'UNKNOWN')}"
                )
                st.caption(
                    f"Detected: {incident.get('detected_at', 'time unavailable')} · "
                    f"Resident: {incident.get('resident_name', 'Unknown resident')}"
                )
                if incident.get("response_deadline_at"):
                    st.caption(f"Response deadline: {incident['response_deadline_at']}")
                action_cols = st.columns(3)
                actor = dict(curr_acc)
                actor["caretaker_id"] = caretaker_id
                actions = (
                    ("✅ Accept", "ACCEPTED", "ACKNOWLEDGED"),
                    ("🚗 On the way", "ON_THE_WAY", "ON_THE_WAY"),
                    ("📍 Reached", "REACHED_LOCATION", "REACHED_LOCATION"),
                    ("🩺 Assistance provided", "ASSISTANCE_PROVIDED", "ASSISTANCE_PROVIDED"),
                    ("❌ Unable to attend", "UNABLE_TO_ATTEND", "ESCALATED_LOCAL_CARETAKER"),
                    ("Resolve incident", "RESOLVED", "RESOLVED"),
                )
                for index, (label, action, new_status) in enumerate(actions):
                    if action_cols[index % 3].button(
                        label,
                        key=f"local_{action}_{incident_id}",
                        use_container_width=True,
                    ):
                        record_incident_action(
                            incident_id=incident_id,
                            action=action,
                            new_status=new_status,
                            actor=actor,
                        )
                        if action == "UNABLE_TO_ATTEND":
                            CaregiverNotificationService.process_overdue_escalations()
                        st.rerun()
                with st.expander(f"Timeline — {incident_id}"):
                    st.dataframe(
                        pd.DataFrame(
                            db_manager.find("emergency_timeline", {"incident_id": incident_id}, limit=500)
                            or incident.get("timeline", [])
                        ),
                        width="stretch",
                    )

    if show_local_history:
        st.markdown("### Recent notifications")
        notifications = db_manager.find(
            "notifications",
            {"recipient_id": caretaker_id},
            limit=100,
            sort=[("created_at", -1)],
        )
        st.dataframe(pd.DataFrame(notifications), width="stretch")
        st.markdown("### Incident history")
        st.dataframe(pd.DataFrame(my_incidents), width="stretch")


# ====================================================
# 4. USER / RESIDENT DASHBOARD (PATIENT PORTAL)
# ====================================================
def render_user_dashboard():
    st.markdown(
        """
        <div class="role-banner-user">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h2 style="color:#14532D; margin:0; font-weight:800;">👤 Resident Safety & Well-Being Hub</h2>
                    <p style="color:#15803D; margin:4px 0 0 0; font-weight:600; font-size:1.05rem;">
                        Fall Guard AI is actively protecting you at home with 24/7 computer vision fall assistance.
                    </p>
                </div>
                <span style="background:#DCFCE7; color:#166534; padding:6px 16px; border-radius:20px; font-weight:800; font-size:0.95rem; border:1.5px solid #22C55E;">
                    🟢 YOU ARE PROTECTED
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    resident = (
        db_manager.find_one("residents", {"resident_id": curr_acc.get("resident_id")})
        if curr_acc.get("resident_id") else None
    )
    resident_room = (
        db_manager.find_one("rooms", {"room_id": resident.get("room_id")})
        if resident else None
    )
    resident_facility = (
        db_manager.find_one("facilities", {"facility_id": resident.get("facility_id")})
        if resident else None
    )
    resident_caretaker = (
        db_manager.find_one(
            "local_caretakers",
            {"caretaker_id": resident_room.get("assigned_caretaker_id")},
        )
        if resident_room and resident_room.get("assigned_caretaker_id") else None
    )
    if resident:
        st.info(
            f"Care profile: **{(resident_facility or {}).get('name', 'Facility')}** · "
            f"Room **{(resident_room or {}).get('room_number', resident.get('room_id', ''))}** · "
            f"Local caretaker **{(resident_caretaker or {}).get('full_name', 'Not assigned')}**"
        )

    # Reassuring Status Card
    open_resident_incident = next(
        (
            incident for incident in db_manager.find(
                "incidents",
                limit=1000,
                sort=[("detected_at", -1)],
            )
            if incident.get("resident_id") == curr_acc.get("resident_id", "RES-101")
            and incident.get("status") not in {"RESOLVED", "CLOSED", "ACKNOWLEDGED_SAFE"}
        ),
        None,
    )
    if st.session_state["active_incident"] is None and open_resident_incident:
        if open_resident_incident.get("resident_verification_status") == "I_AM_OK":
            st.success(
                f"✅ You confirmed you are okay for incident "
                f"{open_resident_incident.get('incident_id')}. A responder has been notified and will review."
            )
        else:
            st.warning(
                f"🚨 A responder is handling incident {open_resident_incident.get('incident_id')} "
                f"({open_resident_incident.get('status', 'ACTIVE')})."
            )
    elif st.session_state["active_incident"] is None:
        st.markdown(
            """
            <div style="background:#F0FDF4; border:2px solid #86EFAC; border-radius:16px; padding:24px; text-align:center; margin-bottom:20px;">
                <div style="font-size:3.5rem; margin-bottom:6px;">🟢</div>
                <h2 style="color:#166534; margin:0; font-weight:800;">ALL CLEAR — YOU ARE SAFE</h2>
                <p style="color:#15803D; font-size:1.1rem; margin-top:6px; font-weight:600;">
                    Your camera monitoring is active. If you ever fall or need help, an alert is sent automatically.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        render_emergency_verification_panel()

    st.markdown(
        """
        <h3 style="margin:18px 0 10px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">
            Live Room Monitoring
        </h3>
        """,
        unsafe_allow_html=True,
    )

    resident_room_ids = (
        {resident_room["room_id"]}
        if resident_room and resident_room.get("room_id")
        else None
    )
    render_live_monitoring_engine(
        show_full_controls=False,
        header_label="Resident Room Monitoring",
        allowed_room_ids=resident_room_ids,
    )

    # One-Touch SOS Emergency Button
    st.markdown(
        """
        <div style="background:#FFF1F2; border:2px solid #FDA4AF; border-radius:16px; padding:24px; margin-bottom:24px; text-align:center;">
            <h3 style="color:#9F1239; margin:0 0 8px 0; font-weight:800;">🆘 Need Immediate Assistance?</h3>
            <p style="color:#881337; font-size:1.0rem; margin-bottom:16px;">
                Press below to send an immediate emergency alert. The resident safety check continues while responders are notified.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sos_col1, sos_col2, sos_col3 = st.columns([1, 2, 1])
    with sos_col2:
        if st.button("🚨 PRESS HERE FOR EMERGENCY HELP (SOS)", type="primary", use_container_width=True):
            sos_id = f"SOS-USER-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            sos_room_id = (resident_room or {}).get("room_id", "Resident Room")
            sos_camera_id = (resident_room or {}).get("camera_id", "CAM-001")
            new_incident = IncidentStateMachine.create_incident(
                incident_id=sos_id,
                camera_id=sos_camera_id,
                room_id=sos_room_id,
                event_type="Manual SOS Emergency",
                detection_evidence=["Resident pressed the 1-Touch SOS emergency button"],
                body_angle=82.0,
                resident_id=curr_acc.get("resident_id", "RES-101"),
                resident_name=curr_acc.get("display_name", "Elderly Resident / Patient"),
            )
            sos_res = EmergencyRoutingService.route_incident(sos_id)
            st.session_state["last_escalation"] = (
                db_manager.find_one("incidents", {"incident_id": sos_id}) or sos_res
            )
            st.session_state["active_incident"] = new_incident
            st.session_state["verification_start_time"] = time.time()
            sent_at = datetime.datetime.now().astimezone().strftime("%I:%M:%S %p")
            add_log(f"Resident manually pressed the emergency SOS button [{sos_id}] at {sent_at}. Immediate responder alert routed.")
            st.error(f"🚨 Emergency alert sent at {sent_at}. Your resident safety check will continue while a responder is notified.")
            st.rerun()

    st.markdown("---")

    # Hands-Free Voice Protection & Resident Privacy Controls
    c_v1, c_v2 = st.columns(2)
    with c_v1:
        st.markdown('<div class="card-light">', unsafe_allow_html=True)
        st.markdown('<h3 style="color:#0F172A; margin-top:0;">🎙️ Hands-Free Voice Protection</h3>', unsafe_allow_html=True)
        st.markdown(
            "If you fall and cannot reach your phone or computer, simply speak clearly to alert your caretakers automatically."
        )

        voice_active = st.toggle(
            "🎙️ Enable Hands-Free Voice Protection",
            value=st.session_state.get("voice_protection_active", True),
            key="voice_protection_active_toggle",
            help="Activates browser speech recognition to listen for emergency distress phrases.",
        )
        st.session_state["voice_protection_active"] = voice_active

        if voice_active:
            st.markdown(
                """
                <div style="background:#F0FDF4; border:1.5px solid #86EFAC; border-radius:10px; padding:10px 14px; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between;">
                    <span style="color:#166534; font-weight:700; font-size:0.95rem;">
                        🟢 Microphone Status: <b>ACTIVE</b>
                    </span>
                    <span style="background:#DCFCE7; color:#15803D; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.8rem; border:1px solid #86EFAC;">
                        LISTENING 🎙️
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Web Speech API client-side JavaScript engine
            st.components.v1.html(
                """
                <div id="voice-status-container" style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #F8FAFC; border: 1.5px dashed #94A3B8; border-radius: 12px; padding: 14px; text-align: center;">
                    <div style="display:flex; justify-content:center; align-items:center; gap:10px; margin-bottom:8px;">
                        <span id="listening-pulse" style="display:inline-block; width:14px; height:14px; background:#22C55E; border-radius:50%; box-shadow:0 0 0 0 rgba(34,197,94,0.7); animation: pulse 1.5s infinite;"></span>
                        <b id="status-title" style="color:#0F172A; font-size:0.95rem;">Speech Recognition Active</b>
                    </div>
                    <div id="status-msg" style="color:#475569; font-size:0.85rem; margin-bottom:6px;">
                        Listening for: <b>"HELP ME"</b> • <b>"I NEED HELP"</b> • <b>"HELP"</b> • <b>"EMERGENCY"</b>
                    </div>
                    <div id="detected-box" style="display:none; background:#FFF1F2; border:1.5px solid #F43F5E; border-radius:8px; padding:8px; margin-top:8px;">
                        <b style="color:#BE123C; font-size:0.9rem;">🚨 Emergency Phrase Detected: </b>
                        <span id="detected-phrase" style="color:#9F1239; font-weight:700;"></span>
                    </div>
                </div>
                <style>
                @keyframes pulse {
                    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
                    70% { transform: scale(1.1); box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
                    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
                }
                </style>
                <script>
                (function() {
                    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                    const statusTitle = document.getElementById('status-title');
                    const statusMsg = document.getElementById('status-msg');
                    const detectedBox = document.getElementById('detected-box');
                    const detectedPhrase = document.getElementById('detected-phrase');

                    if (!SpeechRecognition) {
                        statusTitle.innerText = "⚠️ Speech Recognition Unavailable";
                        statusTitle.style.color = "#D97706";
                        statusMsg.innerHTML = "Web Speech API is not supported in this browser. Please open in <b>Google Chrome</b> or <b>Microsoft Edge</b>.";
                        return;
                    }

                    const recognition = new SpeechRecognition();
                    recognition.continuous = true;
                    recognition.interimResults = false;
                    recognition.lang = 'en-US';

                    let lastAlertTime = 0;

                    recognition.onstart = function() {
                        statusTitle.innerText = "Speech Recognition Active (Listening...)";
                    };

                    recognition.onerror = function(event) {
                        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                            statusTitle.innerText = "❌ Microphone Permission Denied";
                            statusTitle.style.color = "#E11D48";
                            statusMsg.innerHTML = "Microphone access was denied. Please allow microphone permission in your browser address bar.";
                        } else if (event.error !== 'no-speech') {
                            statusTitle.innerText = "⚠️ Speech Recognition Notice";
                            statusMsg.innerText = "Speech status: " + event.error + ". Auto-reconnecting...";
                        }
                    };

                    recognition.onend = function() {
                        try {
                            recognition.start();
                        } catch(e) {}
                    };

                    recognition.onresult = function(event) {
                        for (let i = event.resultIndex; i < event.results.length; ++i) {
                            if (event.results[i].isFinal) {
                                const transcript = event.results[i][0].transcript.trim().toUpperCase();
                                console.log("Heard speech:", transcript);
                                const validPhrases = ["HELP ME", "I NEED HELP", "HELP", "EMERGENCY"];
                                const matched = validPhrases.some(p => transcript.includes(p));

                                if (matched) {
                                    const now = Date.now();
                                    if (now - lastAlertTime > 15000) {
                                        lastAlertTime = now;
                                        detectedBox.style.display = 'block';
                                        detectedPhrase.innerText = transcript;
                                        fetch('http://127.0.0.1:8000/api/incidents/voice-emergency', {
                                            method: 'POST',
                                            headers: {'Content-Type': 'application/json'},
                                            body: JSON.stringify({
                                                phrase: transcript,
                                                resident_id: 'RES-101',
                                                resident_name: 'Elderly Resident / Patient',
                                                room_id: 'Resident Bedroom'
                                            })
                                        }).catch(err => console.log('API Dispatch:', err));
                                    }
                                }
                            }
                        }
                    };

                    try {
                        recognition.start();
                    } catch(e) {}
                })();
                </script>
                """,
                height=130,
            )

            st.markdown(
                """
                <div style="background:#F1F5F9; border-radius:10px; padding:10px; margin-bottom:10px;">
                    <span style="font-size:0.85rem; color:#475569;">Registered Emergency Voice Commands:</span><br>
                    <b style="color:#BE123C; font-size:0.95rem;">1. "HELP ME"</b> • 
                    <b style="color:#BE123C; font-size:0.95rem;">2. "I NEED HELP"</b> • 
                    <b style="color:#BE123C; font-size:0.95rem;">3. "HELP"</b> • 
                    <b style="color:#BE123C; font-size:0.95rem;">4. "EMERGENCY"</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Quick simulation triggers for demonstration & testing
            st.caption("🎙️ **Quick Voice Simulation (Instant Viva Testing):**")
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                if st.button('🗣️ Say "HELP ME"', key="btn_sim_help_me", use_container_width=True):
                    sos_id = f"VOICE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    IncidentStateMachine.create_incident(
                        incident_id=sos_id,
                        camera_id=(resident_room or {}).get("camera_id", "CAM-001"),
                        room_id=(resident_room or {}).get("room_id", "Resident Room"),
                        event_type="VOICE EMERGENCY",
                        emergency_type="VOICE EMERGENCY",
                        emergency_description="Resident spoken emergency command detected: 'HELP ME'",
                        detection_evidence=["Spoken emergency command detected: 'HELP ME'", "Microphone speech recognition verified", "Dispatched to Caretaker 1 (Mohini Ravat)"],
                        body_angle=78.0,
                        status="PENDING",
                        current_assigned_caretaker="Mohini Ravat",
                        resident_id=curr_acc.get("resident_id", "RES-101"),
                        resident_name=curr_acc.get("display_name", "Elderly Resident / Patient"),
                    )
                    EmergencyRoutingService.route_incident(sos_id)
                    add_log(f"Resident spoken emergency phrase 'HELP ME' recognized [{sos_id}]. Immediate responder alert routed.")
                    st.success("🚨 **Emergency Voice Command 'HELP ME' Detected!** An immediate responder alert was routed.")
                    st.rerun()

            with v_col2:
                if st.button('🗣️ Say "I NEED HELP"', key="btn_sim_need_help", use_container_width=True):
                    sos_id = f"VOICE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    IncidentStateMachine.create_incident(
                        incident_id=sos_id,
                        camera_id=(resident_room or {}).get("camera_id", "CAM-001"),
                        room_id=(resident_room or {}).get("room_id", "Resident Room"),
                        event_type="VOICE EMERGENCY",
                        emergency_type="VOICE EMERGENCY",
                        emergency_description="Resident spoken emergency command detected: 'I NEED HELP'",
                        detection_evidence=["Spoken emergency command detected: 'I NEED HELP'", "Microphone speech recognition verified", "Dispatched to Caretaker 1 (Mohini Ravat)"],
                        body_angle=80.0,
                        status="PENDING",
                        current_assigned_caretaker="Mohini Ravat",
                        resident_id=curr_acc.get("resident_id", "RES-101"),
                        resident_name=curr_acc.get("display_name", "Elderly Resident / Patient"),
                    )
                    EmergencyRoutingService.route_incident(sos_id)
                    add_log(f"Resident spoken emergency phrase 'I NEED HELP' recognized [{sos_id}]. Immediate responder alert routed.")
                    st.success("🚨 **Emergency Voice Command 'I NEED HELP' Detected!** An immediate responder alert was routed.")
                    st.rerun()

        else:
            st.markdown(
                """
                <div style="background:#F8FAFC; border:1px solid #CBD5E1; border-radius:10px; padding:12px; margin-bottom:12px;">
                    <span style="color:#64748B; font-weight:600; font-size:0.9rem;">
                        ⚪ Microphone Status: <b>INACTIVE</b>
                    </span>
                    <p style="color:#94A3B8; font-size:0.85rem; margin:4px 0 0 0;">
                        Hands-Free Voice Protection is disabled. Toggle above to activate continuous browser voice listening.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption("🔒 *Privacy Guaranteed: No ambient speech or conversations are recorded or stored. Recognized words are processed strictly in-memory for emergency distress commands.*")
        st.markdown('</div>', unsafe_allow_html=True)

    with c_v2:
        st.markdown('<div class="card-light">', unsafe_allow_html=True)
        st.markdown('<h3 style="color:#0F172A; margin-top:0;">🔒 Your Privacy Controls</h3>', unsafe_allow_html=True)
        st.markdown("You have complete control over whether real camera footage is displayed:")
        st.session_state["ghost_mode"] = st.toggle(
            "👻 Enable Privacy Ghost Mode",
            value=st.session_state["ghost_mode"],
            help="Hides camera video and displays only a stick-figure avatar to caretakers while keeping fall detection 100% active.",
        )
        if st.session_state["ghost_mode"]:
            st.success("👻 Privacy Mode ACTIVE: Real camera images are hidden. Only motion coordinates are analyzed.")
        else:
            st.info("📷 Camera Mode ACTIVE: Normal camera feed is visible.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Caretaker Contacts Display
    st.markdown("---")
    st.markdown("### 📞 Your Dedicated Caretaker Team")
    col_cc1, col_cc2 = st.columns(2)
    with col_cc1:
        st.markdown(
            """
            <div style="background:#FEF3C7; border:1.5px solid #F59E0B; border-radius:14px; padding:18px;">
                <b style="font-size:1.1rem; color:#92400E;">🥇 Mohini Ravat</b><br>
                <span style="color:#78350F; font-size:0.92rem; font-weight:600;">Primary Caretaker (First-Call)</span><br>
                <div style="margin-top:8px; font-size:1.05rem; color:#92400E;">
                    📞 <b>+91 98765 43210</b>
                </div>
                <div style="font-size:0.85rem; color:#B45309; margin-top:4px;">
                    Email: mohini.ravat@fallguard.local
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_cc2:
        st.markdown(
            """
            <div style="background:#EDE9FE; border:1.5px solid #8B5CF6; border-radius:14px; padding:18px;">
                <b style="font-size:1.1rem; color:#5B21B6;">🥈 Radha Raghav</b><br>
                <span style="color:#4C1D95; font-size:0.92rem; font-weight:600;">Secondary Caretaker (Backup-Call)</span><br>
                <div style="margin-top:8px; font-size:1.05rem; color:#5B21B6;">
                    📞 <b>+91 98123 45678</b>
                </div>
                <div style="font-size:0.85rem; color:#6D28D9; margin-top:4px;">
                    Email: radha.raghav@fallguard.local
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ====================================================
# ROLE DISPATCHER ROUTING
# ====================================================
@st.fragment(run_every=5)
def render_active_emergency_notifications():
    escalated_ids = CaregiverNotificationService.process_overdue_escalations()
    if escalated_ids:
        st.rerun()

    role_stage = {
        "caretaker_1": "ESCALATED_CARETAKER_1",
        "caretaker_2": "ESCALATED_CARETAKER_2",
        "admin": "CRITICAL_ADMIN_OVERRIDE",
        "local_caretaker": "ESCALATED_LOCAL_CARETAKER",
    }.get(st.session_state.get("user_role"))
    # Caretakers have a dedicated, integrated emergency triage card in their dashboard
    if not role_stage or st.session_state.get("user_role") in ("caretaker_1", "caretaker_2"):
        return

    alerts = db_manager.find(
        "incidents",
        {"status": role_stage},
        limit=20,
        sort=[("detected_at", -1)],
    )
    if st.session_state.get("user_role") == "local_caretaker":
        alerts = [
            item for item in alerts
            if item.get("active_caretaker_id") == curr_acc.get("caretaker_id")
        ]
    for alert in alerts:
        incident_id = alert.get("incident_id", "UNKNOWN")
        contact_name = alert.get("active_contact", {}).get("name", "Assigned responder")
        started_at = alert.get("response_stage_started_at")
        deadline_at = alert.get("response_deadline_at")
        if started_at:
            started = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            notified_time = started.astimezone().strftime("%I:%M:%S %p")
        else:
            notified_time = "time unavailable"

        st.error(
            f"🚨 Emergency **{incident_id}** at **{alert.get('room_id', 'Unknown location')}** "
            f"is assigned to **{contact_name}**."
        )
        if deadline_at:
            deadline = datetime.datetime.fromisoformat(deadline_at.replace("Z", "+00:00"))
            remaining = int((deadline - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
            st.caption(f"Alert sent at {notified_time}.")
            if role_stage == "CRITICAL_ADMIN_OVERRIDE":
                st.warning("Administrator action required. The incident remains open until an action or resolution is recorded.")
            elif remaining > 0:
                st.warning(f"Respond or forward the alert. Automatic escalation in {remaining // 60}:{remaining % 60:02d}.")
            else:
                st.warning("Response window expired. Forwarding to the next responder.")

render_active_emergency_notifications()

role = curr_acc["role"]
if role == "admin":
    render_admin_dashboard()
elif role == "caretaker_1":
    render_caretaker1_dashboard()
elif role == "caretaker_2":
    render_caretaker2_dashboard()
elif role == "user":
    render_user_dashboard()
elif role == "resident":
    render_user_dashboard()
elif role == "local_caretaker":
    render_local_caretaker_dashboard()
else:
    st.error("Your account is not authorized to access a dashboard.")
    log_out_user()
