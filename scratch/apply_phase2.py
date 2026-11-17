import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# ----------------------------------------------------
# 1. REPLACE GlobalCameraHub (and remove SyntheticResults)
# ----------------------------------------------------
hub_start = text.find("class SyntheticResults:")
hub_end = text.find("def open_monitoring_camera(camera_index: int):")

if hub_start == -1 or hub_end == -1:
    print("Error: Could not find GlobalCameraHub markers!")
    sys.exit(1)

new_camera_hub = '''class GlobalCameraHub:
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
            if self.latest_frame is None:
                return False, None, self.fps
            return True, self.latest_frame.copy(), self.fps

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


'''

text = text[:hub_start] + new_camera_hub + text[hub_end:]
print("Replaced GlobalCameraHub cleanly.")

# ----------------------------------------------------
# 2. REPLACE render_live_monitoring_engine
# ----------------------------------------------------
engine_start = text.find("def render_live_monitoring_engine(")
engine_end = text.find("def render_admin_override_console():")

if engine_start == -1 or engine_end == -1:
    print("Error: Could not find render_live_monitoring_engine markers!")
    sys.exit(1)

new_engine = '''def render_live_monitoring_engine(
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

    # Ensure background camera is active
    if run_stream and st.session_state.get("active_incident") is None:
        hub = GlobalCameraHub.get_instance()
        hub.start(camera_idx)

    # ----------------------------------------------------
    # Dedicated Self-Contained Fragment for Live Camera & Pose (Image 2 style)
    # ----------------------------------------------------
    @st.fragment(run_every=0.1)
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

        if st.session_state.get("active_incident") is not None:
            st.warning("⏸️ Camera stream paused during Emergency Verification. Confirm status above.")
            return

        hub = GlobalCameraHub.get_instance()
        if not hub.is_active():
            started, _, error_message = hub.start(camera_idx)
            if not started:
                st.error(
                    f"Camera not available, check device index or permissions. ({error_message or hub.capture_status})"
                )
                return

        success, frame, cam_fps = hub.read_frame()
        if not success or frame is None:
            st.error(
                f"Camera not available, check device index or permissions. ({hub.capture_status})"
            )
            return

        h, w, _ = frame.shape
        annotated_frame, results = pose_detector.process_frame(frame.copy())
        landmarks = landmark_extractor.extract(results)
        features = feature_calculator.calculate(landmarks)

        curr_t = time.time()
        prev_t = st.session_state.get("_monitoring_previous_frame_time", curr_t)
        fps = 1.0 / (curr_t - prev_t) if (curr_t - prev_t) > 0 else cam_fps
        if fps <= 0:
            fps = cam_fps if cam_fps > 0 else 9.7
        st.session_state["_monitoring_previous_frame_time"] = curr_t

        temporal_res = temporal_detector.update(features, timestamp=curr_t)
        posture = temporal_res["posture"]
        is_possible_fall = temporal_res["is_possible_fall"]
        velocity = temporal_res["velocity"]
        evidence_points = temporal_res["explanation_evidence"]
        body_angle = features.get("body_angle_degrees") if features else None
        body_angle_text = f"{body_angle:.1f}°" if body_angle is not None else "Waiting for pose"
        mean_vis = features.get("mean_visibility", 0.0) if features else 0.0

        display_frame = annotated_frame.copy()
        if st.session_state.get("ghost_mode"):
            ghost_canvas = np.full((h, w, 3), 25, dtype=np.uint8)
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

        # Overlays matching Image 2 & test_pose.py
        if is_possible_fall:
            cv2.putText(display_frame, "ALERT: FALL DETECTED!", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.90, (0, 0, 255), 3, cv2.LINE_AA)
        elif landmarks is not None:
            cv2.putText(display_frame, f"STATUS: {posture.upper()}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (0, 255, 0), 2, cv2.LINE_AA)
        else:
            cv2.putText(display_frame, "STATUS: SEARCHING FOR PERSON", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (160, 160, 160), 2, cv2.LINE_AA)

        cv2.putText(display_frame, f"FPS: {fps:.1f}", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

        # Trigger emergency fall incident if verified fall detected
        if is_possible_fall and st.session_state.get("active_incident") is None:
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

        # TOP ALERT BANNER (Matching Image 2 when fall detected)
        if is_possible_fall:
            st.markdown(
                """
                <div style="background:#B91C1C; color:white; padding:12px 20px; border-radius:14px; text-align:center; font-weight:800; font-size:1.15rem; margin-bottom:16px; box-shadow:0 0 25px rgba(220,38,38,0.45); letter-spacing:0.02em;">
                    🚨 CRITICAL EMERGENCY: HUMAN FALL DETECTED! DISPATCHING ASSISTANCE 🚨
                </div>
                """,
                unsafe_allow_html=True,
            )

        # MAIN 2-COLUMN VIEW (Matching Image 2 exactly)
        col_v, col_t = st.columns([13, 9])
        with col_v:
            st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:0 0 8px 0;">📹 Live Camera Stream</h4>', unsafe_allow_html=True)
            cam_box_style = (
                "border: 6px solid #DC2626; border-radius: 8px; box-shadow: 0 0 24px rgba(220, 38, 38, 0.40); overflow:hidden;"
                if is_possible_fall
                else "border: 2px solid #CBD5E1; border-radius: 8px; overflow:hidden;"
            )
            st.markdown(f'<div style="{cam_box_style}">', unsafe_allow_html=True)
            st.image(frame_rgb, channels="RGB", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_t:
            st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:0 0 8px 0;">📊 Live Monitoring Telemetry</h4>', unsafe_allow_html=True)
            badge_person_html = (
                '<span style="background:#DCFCE7; color:#15803D; border:1.5px solid #86EFAC; padding:6px 14px; border-radius:20px; font-weight:800; font-size:0.88rem; display:inline-block; margin-right:8px; margin-bottom:10px;">🟢 Person Detected</span>'
                if landmarks is not None
                else '<span style="background:#F1F5F9; color:#64748B; border:1.5px solid #CBD5E1; padding:6px 14px; border-radius:20px; font-weight:700; font-size:0.88rem; display:inline-block; margin-right:8px; margin-bottom:10px;">⚪ Searching for Person</span>'
            )
            badge_fall_html = (
                '<span style="background:#FEE2E2; color:#B91C1C; border:1.5px solid #FCA5A5; padding:6px 14px; border-radius:20px; font-weight:800; font-size:0.88rem; display:inline-block; margin-bottom:10px;">🚨 FALL DETECTED!</span>'
                if is_possible_fall
                else f'<span style="background:#DCFCE7; color:#15803D; border:1.5px solid #86EFAC; padding:6px 14px; border-radius:20px; font-weight:800; font-size:0.88rem; display:inline-block; margin-bottom:10px;">🟢 {posture.upper() if landmarks else "NORMAL ACTIVITY"}</span>'
            )
            st.markdown(f'<div>{badge_person_html}{badge_fall_html}</div>', unsafe_allow_html=True)

            m1, m2 = st.columns(2)
            m1.metric("Camera FPS", f"{fps:.1f}")
            m2.metric("Torso Angle", body_angle_text)

            st.markdown('<h4 style="color:#0F172A; font-weight:800; margin:18px 0 8px 0;">📱 Emergency SOS Dispatch</h4>', unsafe_allow_html=True)
            em_contact = st.session_state.get("emergency_contact_number", "+1 (555) 019-2834")
            if is_possible_fall:
                st.markdown(
                    f"""
                    <div style="background:#FFF1F2; border:2px solid #FDA4AF; border-radius:14px; padding:18px; box-shadow:0 4px 14px rgba(225,29,72,0.12);">
                        <div style="color:#BE123C; font-weight:850; font-size:1.02rem; margin-bottom:6px;">
                            🚨 EMERGENCY SOS DISPATCHED
                        </div>
                        <div style="color:#881337; font-size:0.90rem; font-weight:600;">
                            Automated Call & SMS dispatched to {em_contact}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="background:#F8FAFC; border:1.5px solid #E2E8F0; border-radius:14px; padding:18px;">
                        <div style="color:#475569; font-weight:750; font-size:0.95rem; margin-bottom:4px;">
                            📱 Emergency SOS Standby
                        </div>
                        <div style="color:#64748B; font-size:0.88rem;">
                            Automated Dispatch ready for {em_contact}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

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


'''

text = text[:engine_start] + new_engine + text[engine_end:]
print("Replaced render_live_monitoring_engine cleanly.")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved phase 2 changes.")
