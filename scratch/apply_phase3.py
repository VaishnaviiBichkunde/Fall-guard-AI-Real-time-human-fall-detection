import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. In render_caretaker_shared_dashboard, update the radio to sync with session_state
old_radio_block = """        caretaker_view_option = st.radio(
            "Care Console Options:",
            [
                "📊 Complete Care Console",
                "Live Room Monitoring 📹",
                "🚨 Emergency Alerts & Triage",
                "👤 Resident Care Profile",
                "👥 Caregiver Duty Roster",
                "📑 Emergency History & Reports",
                "📞 Quick Intercom Directory",
            ],
            key=f"caretaker_sidebar_nav_view_{tier}",
            label_visibility="collapsed",
        )"""

new_radio_block = """        options_list = [
            "📊 Complete Care Console",
            "Live Room Monitoring 📹",
            "🚨 Emergency Alerts & Triage",
            "👤 Resident Care Profile",
            "👥 Caregiver Duty Roster",
            "📑 Emergency History & Reports",
            "📞 Quick Intercom Directory",
        ]
        caretaker_nav_key = f"caretaker_selected_nav_{tier}"
        if caretaker_nav_key not in st.session_state:
            st.session_state[caretaker_nav_key] = options_list[0]
        if st.session_state[caretaker_nav_key] not in options_list:
            st.session_state[caretaker_nav_key] = options_list[0]

        caretaker_view_option = st.radio(
            "Care Console Options:",
            options_list,
            index=options_list.index(st.session_state[caretaker_nav_key]),
            key=f"caretaker_sidebar_radio_{tier}",
            label_visibility="collapsed",
        )
        st.session_state[caretaker_nav_key] = caretaker_view_option"""

if old_radio_block in text:
    text = text.replace(old_radio_block, new_radio_block, 1)
    print("Updated Caretaker sidebar radio block.")
else:
    print("Warning: old_radio_block not found!")

# 2. Update the show_* booleans so show_emergency isn't forced by active_inc
old_booleans = """    show_all = (caretaker_view_option == "📊 Complete Care Console")
    show_live = show_all or (caretaker_view_option == "Live Room Monitoring 📹")
    show_emergency = show_all or (caretaker_view_option == "🚨 Emergency Alerts & Triage") or (active_inc is not None)
    show_resident = show_all or (caretaker_view_option == "👤 Resident Care Profile")
    show_roster = show_all or (caretaker_view_option == "👥 Caregiver Duty Roster")
    show_history = show_all or (caretaker_view_option == "📑 Emergency History & Reports")
    show_intercom = show_all or (caretaker_view_option == "📞 Quick Intercom Directory")"""

new_booleans = """    show_all = (caretaker_view_option == "📊 Complete Care Console")
    show_live = show_all or (caretaker_view_option == "Live Room Monitoring 📹")
    show_emergency = show_all or (caretaker_view_option == "🚨 Emergency Alerts & Triage")
    show_resident = show_all or (caretaker_view_option == "👤 Resident Care Profile")
    show_roster = show_all or (caretaker_view_option == "👥 Caregiver Duty Roster")
    show_history = show_all or (caretaker_view_option == "📑 Emergency History & Reports")
    show_intercom = show_all or (caretaker_view_option == "📞 Quick Intercom Directory")"""

if old_booleans in text:
    text = text.replace(old_booleans, new_booleans, 1)
    print("Updated Caretaker show_* booleans.")
else:
    print("Warning: old_booleans not found!")

# 3. Remove duplicate logout button in Caretaker dashboard header
old_logout_block = """    # Header Controls (Duty notification & Sign out)
    head_c1, head_c2 = st.columns([20, 4])
    with head_c1:
        if not my_avail:
            if is_c1:
                st.warning("⚠️ You are currently **OFF-DUTY**. Incoming patient emergencies automatically route to **Radha Raghav (Caretaker 2)**.")
            else:
                st.warning("⚠️ You are currently **OFF-DUTY**. If Mohini Ravat is also unavailable, emergency calls escalate to the **System Administrator**.")
        else:
            if not is_c1 and not is_mohini_avail:
                st.warning("⚠️ **Mohini Ravat (Caretaker 1) is OFF-DUTY.** You (Radha Raghav) are actively serving as the **PRIMARY FIRST RESPONDER**.")
    with head_c2:
        if st.button("🚪 Logout", key=f"btn_logout_top_{tier}", use_container_width=True):
            log_out_user()"""

new_logout_block = """    # Duty notification (Single global logout button is in the top bar)
    if not my_avail:
        if is_c1:
            st.warning("⚠️ You are currently **OFF-DUTY**. Incoming patient emergencies automatically route to **Radha Raghav (Caretaker 2)**.")
        else:
            st.warning("⚠️ You are currently **OFF-DUTY**. If Mohini Ravat is also unavailable, emergency calls escalate to the **System Administrator**.")
    else:
        if not is_c1 and not is_mohini_avail:
            st.warning("⚠️ **Mohini Ravat (Caretaker 1) is OFF-DUTY.** You (Radha Raghav) are actively serving as the **PRIMARY FIRST RESPONDER**.")"""

if old_logout_block in text:
    text = text.replace(old_logout_block, new_logout_block, 1)
    print("Removed duplicate logout button in Caretaker header.")
else:
    print("Warning: old_logout_block not found!")

# 4. Remove duplicate camera button in Caretaker dashboard
old_cam_block = """    if show_live:
        sub_c1, sub_c2 = st.columns([22, 2])
        with sub_c1:
            st.markdown(
                \"\"\"
                <h3 style="margin:18px 0 10px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">
                    Live Patient-Room Monitoring
                </h3>
                \"\"\",
                unsafe_allow_html=True,
            )
        with sub_c2:
            st.markdown('<div style="padding-top:14px;">', unsafe_allow_html=True)
            c_icon = "📹" if st.session_state.get("stream_active", True) else "📷"
            c_help = "Live Camera Active — Click to pause" if st.session_state.get("stream_active", True) else "Camera Paused — Click to resume"
            if st.button(c_icon, key=f"btn_header_cam_caretaker_{tier}", help=c_help):
                new_state = not st.session_state.get("stream_active", True)
                st.session_state["stream_active"] = new_state
                if not new_state:
                    GlobalCameraHub.get_instance().stop()
                else:
                    GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        render_live_monitoring_engine(
            show_full_controls=False,
            header_label="Patient Room Monitoring",
        )"""

new_cam_block = """    if show_live:
        st.markdown(
            \"\"\"
            <h3 style="margin:18px 0 10px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">
                Live Patient-Room Monitoring
            </h3>
            \"\"\",
            unsafe_allow_html=True,
        )
        render_live_monitoring_engine(
            show_full_controls=True,
            header_label="Patient Room Monitoring",
        )"""

if old_cam_block in text:
    text = text.replace(old_cam_block, new_cam_block, 1)
    print("Removed duplicate camera button in Caretaker dashboard.")
else:
    print("Warning: old_cam_block not found!")

# 5. Guard emergency status section with if show_emergency:
old_em_header = """    # ----------------------------------------------------
    # 2. EMERGENCY STATUS — MOST IMPORTANT SECTION
    # ----------------------------------------------------
    active_count = len([
        i for i in all_incidents
        if i.get("status") in ["PENDING", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "ACKNOWLEDGED"]
    ])
    pending_count = pending_alerts_count

    if active_inc:"""

new_em_header = """    # ----------------------------------------------------
    # 2. EMERGENCY STATUS & TRIAGE SECTION
    # ----------------------------------------------------
    active_count = len([
        i for i in all_incidents
        if i.get("status") in ["PENDING", "ESCALATED_CARETAKER_1", "ESCALATED_CARETAKER_2", "ACKNOWLEDGED"]
    ])
    pending_count = pending_alerts_count

    if show_emergency:
        st.markdown('<h3 style="margin:20px 0 12px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">🚨 Emergency Alerts & Triage</h3>', unsafe_allow_html=True)
        if active_inc:"""

if old_em_header in text:
    # Need to indent the active_inc block or structure it inside if show_emergency:
    # Let's check how active_inc and else: are indented
    print("Found old_em_header.")
else:
    print("Warning: old_em_header not found!")

# 6. Remove duplicate camera button in Resident/User dashboard
old_user_cam_block = """    sub_u1, sub_u2 = st.columns([22, 2])
    with sub_u1:
        st.markdown(
            \"\"\"
            <h3 style="margin:18px 0 10px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">
                Live Room Monitoring
            </h3>
            \"\"\",
            unsafe_allow_html=True,
        )
    with sub_u2:
        st.markdown('<div style="padding-top:14px;">', unsafe_allow_html=True)
        u_icon = "📹" if st.session_state.get("stream_active", True) else "📷"
        u_help = "Live Camera Active — Click to pause" if st.session_state.get("stream_active", True) else "Camera Paused — Click to resume"
        if st.button(u_icon, key="btn_header_cam_user", help=u_help):
            new_state = not st.session_state.get("stream_active", True)
            st.session_state["stream_active"] = new_state
            if not new_state:
                GlobalCameraHub.get_instance().stop()
            else:
                GlobalCameraHub.get_instance().start(st.session_state.get("camera_hw_index", 0))
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)"""

new_user_cam_block = """    st.markdown(
        \"\"\"
        <h3 style="margin:18px 0 10px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">
            Live Room Monitoring
        </h3>
        \"\"\",
        unsafe_allow_html=True,
    )"""

if old_user_cam_block in text:
    text = text.replace(old_user_cam_block, new_user_cam_block, 1)
    print("Removed duplicate camera button in User dashboard.")
else:
    print("Warning: old_user_cam_block not found!")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved phase 3 changes.")
