import re
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

print("Original app.py length:", len(content))

# 1. Update CSS to ensure sidebar radio buttons are vibrant, clickable, and never faded
css_target = """    [data-testid="stSidebar"] .stRadio label {
        font-weight: 750 !important;
        color: #1E3A8A !important;
        padding: 4px 0;
    }
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {
        color: #1E3A8A !important;
        font-weight: 800 !important;
    }"""

css_replacement = """    [data-testid="stSidebar"] .stRadio {
        opacity: 1 !important;
        pointer-events: auto !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-weight: 750 !important;
        color: #1E3A8A !important;
        padding: 4px 0;
    }
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {
        color: #1E3A8A !important;
        font-weight: 800 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
        opacity: 1 !important;
        cursor: pointer !important;
        color: #1E3A8A !important;
        font-weight: 750 !important;
        background: rgba(255, 255, 255, 0.85);
        padding: 8px 14px !important;
        border-radius: 12px !important;
        margin-bottom: 6px !important;
        border: 1.5px solid #DBEAFE !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {
        background: #EFF6FF !important;
        border-color: #3B82F6 !important;
        color: #1D4ED8 !important;
        transform: translateX(3px);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"],
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
        border-color: #2563EB !important;
        color: #1D4ED8 !important;
        font-weight: 800 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.16) !important;
    }"""

if css_target in content:
    content = content.replace(css_target, css_replacement, 1)
    print("Updated sidebar radio CSS.")
else:
    print("Warning: css_target not found!")

# 2. Update log_out_user()
logout_target = """def log_out_user():
    camera = st.session_state.pop("_monitoring_camera", None)
    if camera is not None:
        if hasattr(camera, "stop"):
            camera.stop()
        else:
            camera.release()
    try:
        GlobalCameraHub.get_instance().stop()
    except Exception:
        pass
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state["user_role"] = ""
    st.session_state["user_display_name"] = ""
    st.session_state.pop("login_username", None)
    st.session_state.pop("login_password", None)
    st.rerun()"""

logout_replacement = """def log_out_user():
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

    # Clear all session state variables thoroughly
    for k in list(st.session_state.keys()):
        del st.session_state[k]

    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state["user_role"] = ""
    st.session_state["user_display_name"] = ""
    st.session_state["active_incident"] = None
    st.session_state["stream_active"] = False

    st.rerun()"""

if logout_target in content:
    content = content.replace(logout_target, logout_replacement, 1)
    print("Updated log_out_user().")
else:
    print("Warning: logout_target not found!")

# 3. Ensure global Sign Out button has unique key
global_signout_target = """with c_signout:
    if st.button("🚪 Sign Out", use_container_width=True):
        log_out_user()"""

global_signout_replacement = """with c_signout:
    if st.button("🚪 Sign Out", key=f"btn_sign_out_global_{curr_acc.get('role', 'user')}", use_container_width=True):
        log_out_user()"""

if global_signout_target in content:
    content = content.replace(global_signout_target, global_signout_replacement, 1)
    print("Updated global Sign Out button.")
else:
    print("Warning: global_signout_target not found!")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Saved phase 1 changes.")
