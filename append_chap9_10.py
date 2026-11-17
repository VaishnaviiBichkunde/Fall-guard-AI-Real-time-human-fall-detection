import os

report_path = r"c:\Users\Hp\OneDrive\Vaishnavi\OneDrive\Desktop\real time human fall detection\DSCASC_MCA_FINAL_PROJECT_REPORT.md"

def append_section_9_10():
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("""
---

# CHAPTER 9
# PLANNING

## 9.1 Overall Description

### 9.1.1 Product Perspective
Fall Guard AI functions as a self-contained, intelligent edge-computing resident safety platform. Unlike commercial cloud-dependent surveillance cameras that stream continuous video feeds across external networks, Fall Guard AI executes all computer vision pose extraction and kinematic decision modeling strictly on the local on-premise computing device.

The product operates within a distributed microservices paradigm consisting of:
1. **Edge Vision Client & Frontend (Streamlit)**: Ingests monocular camera streams, computes local kinematics, manages session states, renders role-based dashboards, and interacts with local audio/touch interfaces.
2. **Asynchronous REST API Gateway (FastAPI)**: Serves machine-to-machine endpoints for incident querying, caregiver registration, camera registration, and remote webhook dispatch.
3. **Resilient Data Store (MongoDB + Local JSON Fallback)**: Persists operational configuration, caregiver rosters, multi-room profiles, and chronological audit timelines.
4. **Outbound Notification Relay (SMTP)**: Direct socket connection to enterprise or local mail servers for real-time dispatch of emergency alerts.

```
       +--------------------------------------------------------------------+
       |                   FALL GUARD AI PRODUCT TOPOLOGY                   |
       +--------------------------------------------------------------------+
                                 [ Domestic Environment ]
                                            |
         +----------------------------------+----------------------------------+
         |                                  |                                  |
         v                                  v                                  v
  [ Living Room Node ]             [ Master Bedroom Node ]            [ Patient Room Node ]
  (Camera 1: USB 640x480)          (Camera 2: Simulated Node)         (Camera 3: Simulated Node)
         |                                  |                                  |
         +----------------------------------+----------------------------------+
                                            |
                                            v (Local Video Frames)
                     +----------------------------------------------+
                     |    Edge Host Device (Fall Guard AI Core)     |
                     |  - OpenCV Frame Acquisition (DSHOW)          |
                     |  - MediaPipe Pose Inference (@ 30 FPS)       |
                     |  - Temporal Motion & Kinematics Engine       |
                     |  - 5-State Verification State Machine        |
                     +----------------------------------------------+
                                            |
                         +------------------+------------------+
                         |                                     |
                         v                                     v
             [ Streamlit Role Portals ]               [ FastAPI REST Engine ]
             - Admin Console                          - /api/incidents
             - Caretaker 1: Mohini Ravat              - /api/caregivers
             - Caretaker 2: Radha Raghav              - /api/cameras
             - Resident / Patient Hub                 - /api/system
                         |                                     |
                         +------------------+------------------+
                                            |
                                            v
                     +----------------------------------------------+
                     |       Dual Resilient Storage Manager         |
                     |  - Primary: MongoDB (fall_guard_ai)          |
                     |  - Fallback: Local JSON Storage (/data/*.json)
                     +----------------------------------------------+
                                            |
                                            v (Trigger Alert on Timeout/SOS)
                     +----------------------------------------------+
                     |     SMTP Multi-Tiered Notification Relay     |
                     |  Tier 1: Mohini Ravat (Primary Caretaker)    |
                     |  Tier 2: Radha Raghav (Secondary Caretaker)  |
                     |  Tier 3: System Administrator Override       |
                     +----------------------------------------------+
```

### 9.1.2 Product Functions
Fall Guard AI delivers eight interconnected core functions designed to solve real-world elderly care challenges:
1. **Smart Fall Detection vs. Normal Activity**: Tracks multi-frame landmark coordinates across time, evaluating torso angles, centroid drop velocities, and aspect ratio deformations to classify seven postures (Standing, Walking, Sitting, Bending, Intentional Lying Down, Uncertain, Possible Fall).
2. **Explainable Fall Detection**: Automatically synthesizes and renders human-interpretable biomechanical evidence items alongside every event (e.g., *"Torso angle inclined 74.5° from vertical"*, *"Rapid drop velocity: 0.048 ΔY/frame"*).
3. **Intelligent Emergency Verification System**: Deploys a 5-state finite state machine with an interactive 15-second countdown modal dialog. Allows conscious fallen individuals to cancel alarms via **"🟢 I'M OK"** or request immediate rescue via **"🔴 I NEED HELP"**.
4. **Voice-Based Emergency Assistance**: Hands-free acoustic recognition allowing patients who cannot reach their keyboard or screen to vocalize *"I'm okay"* or *"Help me"* to control the state machine.
5. **Real-Time Caregiver Alert System**: Conducts truthful SMTP email handshakes, reporting verified delivery statuses (`SENT`, `FAILED`, `NOT_CONFIGURED`) without fabricating success.
6. **Chronological Incident Records & Audit Timeline**: Full CRUD persistence in MongoDB tracking incident IDs, room nodes, body tilt angles, user responses, notification statuses, and sequential event histories.
7. **Camera Node & Multi-Room Management**: Allows administrators to register residential rooms (Living Room, Bedroom, Patient Room) and link them to hardware webcam indices or simulated nodes.
8. **Privacy-Preserving Ghost Mode**: Renders a synthetic digital wireframe skeleton avatar on a dark canvas, completely concealing raw camera images while maintaining 100% detection accuracy.

## 9.2 User Modules

```
+--------------------------------------------------------------------------------------------------+
|                                    USER MODULE ARCHITECTURE                                      |
+---------------------+-------------------+---------------------+----------------------------------+
| Module Name         | Default Account   | Access Role         | Primary Capabilities & Views     |
+---------------------+-------------------+---------------------+----------------------------------+
| 1. System Admin     | admin / admin123  | System Administrator| - Master live CV monitoring feed.|
|    Console          |                   |                     | - Multi-room camera node manager.|
|                     |                   |                     | - Full MongoDB incident history. |
|                     |                   |                     | - Caregiver roster & duty toggles|
|                     |                   |                     | - Algorithm sensitivity sliders. |
+---------------------+-------------------+---------------------+----------------------------------+
| 2. Primary Caretaker| mohini / mohini123| Primary Caretaker   | - Real-time On-Duty toggle switch|
|    Portal           |                   | (Caretaker 1)       | - Emergency action card triage.  |
|                     |                   |                     | - "I Am Attending" action.       |
|                     |                   |                     | - "Forward to Radha" failover.   |
|                     |                   |                     | - Live patient check-in stream.  |
+---------------------+-------------------+---------------------+----------------------------------+
| 3. Secondary Backup | radha / radha123  | Secondary Caretaker | - Backup readiness duty toggle.  |
|    Portal           |                   | (Caretaker 2)       | - Primary caretaker watch status.|
|                     |                   |                     | - Escalated failover alert card. |
|                     |                   |                     | - "Escalate to Admin Override".  |
|                     |                   |                     | - Live patient check-in stream.  |
+---------------------+-------------------+---------------------+----------------------------------+
| 4. Resident /       | user / user123    | Monitored Patient / | - Reassuring "YOU ARE SAFE" card.|
|    Patient Portal   |                   | Elderly Senior      | - One-touch red emergency SOS.   |
|                     |                   |                     | - Hands-free voice guide prompt. |
|                     |                   |                     | - Ghost Mode privacy switch.     |
|                     |                   |                     | - Dedicated caretaker contacts.  |
+---------------------+-------------------+---------------------+----------------------------------+
```

## 9.3 Functional and Non-Functional Requirements

### 9.3.1 Detailed Functional Requirements (FR)
- **FR-01 (Frame Ingestion)**: System shall capture video frames from local USB optical devices using OpenCV DirectShow at a native resolution of $640 \times 480$ pixels at $\ge 25$ FPS.
- **FR-02 (Pose Extraction)**: System shall extract 33 topological landmark coordinates $(x, y, z, v)$ per frame using MediaPipe Pose.
- **FR-03 (Torso Angle Calculation)**: System shall calculate the torso inclination angle relative to the vertical axis via vector dot product of the shoulder and hip midpoints.
- **FR-04 (Descent Velocity Calculation)**: System shall compute the normalized vertical centroid drop velocity $v_{\Delta Y}$ across successive frames.
- **FR-05 (Posture Classification)**: System shall categorize human posture into one of seven classes: Standing, Sitting, Bending, Walking, Intentional Lying Down, Uncertain, or Possible Fall.
- **FR-06 (ADL Suppression)**: System shall suppress emergency alerts during controlled bending, sitting, or slow transitions into bed where velocity $v_{\Delta Y} < 0.020$.
- **FR-07 (Fall Trigger)**: System shall register a "Possible Fall" when torso inclination $\ge 38^\circ$ and descent velocity $v_{\Delta Y} \ge 0.035$ persists for $\ge 3$ consecutive frames.
- **FR-08 (Emergency Verification Panel)**: Upon fall detection, system shall display an emergency panel with a pulsating countdown timer (default 15 seconds).
- **FR-09 (Verification User Response)**: If the user selects "🟢 I'M OK", the system shall immediately transition the incident to `RESOLVED_SAFE` and reset the monitor.
- **FR-10 (Manual Help Trigger)**: If the user selects "🔴 I NEED HELP", the system shall transition to `HELP_REQUESTED` and trigger immediate caregiver escalation.
- **FR-11 (Countdown Timeout Escalation)**: If the countdown reaches 0 seconds without response, the system shall automatically initiate emergency escalation.
- **FR-12 (Voice Command Recognition)**: System shall recognize speech inputs ("I am okay", "Help me") as identical functional equivalents to on-screen buttons.
- **FR-13 (Tier 1 Notification)**: System shall attempt dispatch to Caretaker 1 (Mohini Ravat) as the primary first responder.
- **FR-14 (Tier 2 Failover)**: If Caretaker 1 is toggled Off-Duty or forwards the call, system shall automatically reroute the alert to Caretaker 2 (Radha Raghav).
- **FR-15 (Tier 3 Admin Override)**: If both Caretaker 1 and Caretaker 2 are off-duty or fail to respond, system shall escalate directly to the System Administrator.
- **FR-16 (Ghost Mode Rendering)**: System shall allow toggling Ghost Mode, concealing camera imagery and drawing an interactive wireframe skeleton on a dark canvas.
- **FR-17 (MongoDB Persistence)**: System shall persist all incidents, timestamps, detection evidence, and timeline events in the MongoDB `incidents` collection.
- **FR-18 (Local JSON Fallback)**: If MongoDB connection fails, system shall transparently cache and retrieve all data from local JSON storage files in `/data`.
- **FR-19 (Multi-Room Support)**: System shall permit administrative registration of room locations (Living Room, Bedroom, Patient Room) linked to camera indices.
- **FR-20 (One-Touch Resident SOS)**: Resident portal shall feature an emergency SOS button that immediately dispatches notifications to both caregivers.

### 9.3.2 Non-Functional Requirements (NFR)
- **NFR-01 (Inference Latency)**: Total per-frame processing latency (capture + MediaPipe + kinematics) must not exceed 40 milliseconds on standard CPU hardware.
- **NFR-02 (Availability & Reliability)**: System must sustain continuous 24/7 execution without memory leaks, process crashes, or MediaPipe C++ runtime aborts.
- **NFR-03 (Fault Tolerance)**: System must guarantee zero data loss during database server dropouts via atomic local JSON fallback writing.
- **NFR-04 (Privacy & Ethical Compliance)**: Raw video images must never be saved to persistent disk by default or transmitted across public networks.
- **NFR-05 (Truthful Notification Reporting)**: System must never claim an email alert has been delivered unless the SMTP server returns an explicit RFC 5321 completion code.
- **NFR-06 (Usability & Accessibility)**: High-contrast typography ($\ge 4.5:1$ contrast ratio) and minimum button dimensions ($>60\text{px}$ height) to accommodate elderly motor limitations.
- **NFR-07 (Modularity)**: Strict separation of concerns between vision extraction (`core/`), database adapters (`backend/`), and user interface (`app.py`).
- **NFR-08 (Test Coverage)**: Automated test suite must maintain 100% pass rate across core kinematic and state machine assertions.
- **NFR-09 (Scalability)**: Architecture must support expansion to multi-camera residential network arrays without refactoring the core state machine.
- **NFR-10 (Recoverability)**: Following an unexpected power interruption, system must restart and restore previous caregiver rosters and room configs within 5 seconds.

---

# CHAPTER 10
# SYSTEM DESIGN

## 10.1 System Perspective & Architectural Block Diagram
The architectural block diagram illustrates the end-to-end data processing pipeline of Fall Guard AI, demonstrating how raw photons captured by optical sensors are transformed through layered abstraction into actionable emergency dispatch workflows.

```
+---------------------------------------------------------------------------------------------------------+
|                                  FALL GUARD AI ARCHITECTURAL BLOCK DIAGRAM                              |
+---------------------------------------------------------------------------------------------------------+

  [ OPTICAL SENSOR ] =====> [ OPENCV INGESTION ] =====> [ MEDIAPIPE POSE ] =====> [ KINEMATIC FEATURE ENGINE ]
  (USB Webcam 30 FPS)       - cv2.CAP_DSHOW             - BlazePose CPU           - Torso Inclination Angle (θ)
                            - 640 x 480 BGR to RGB      - 33 3D Landmarks         - Normalized Drop Velocity (v_ΔY)
                            - Thread-Safe Lock          - (x, y, z, visibility)   - Aspect Ratio (Φ = W/H)
                                                                                                 |
                                                                                                 v
  [ ROLE DASHBOARDS ] <==== [ 5-STATE VERIFICATION MACHINE ] <==== [ TEMPORAL MOTION DETECTOR ] <+
  - System Admin            - 15s Countdown Timer                  - 7-State Posture Classifier
  - Caretaker 1 (Mohini)    - Touch: "I'M OK" / "I NEED HELP"      - ADL Suppression (Bending, Sitting, Bed)
  - Caretaker 2 (Radha)     - Voice: "Help me" / "I'm okay"        - Sliding Temporal Window (N ≥ 3 frames)
  - Resident (User SOS)     - Auto-Escalation on Timeout           - Explainable Evidence Synthesis
            |                               |
            v                               v
  [ DUAL RESILIENT STORAGE ]      [ TIERED CAREGIVER ESCALATION ENGINE ]
  - MongoDB (fall_guard_ai)       - Tier 1: Mohini Ravat (Primary Caretaker)
  - Local JSON Fallback (/data)   - Tier 2: Radha Raghav (Secondary Backup Failover)
  - Indexes on ID, Room, Time     - Tier 3: System Administrator (Critical Override)
  - Complete Audit Timelines      - Real SMTP Relay (RFC 5321 Truthful Status)
```

## 10.2 Data Flow Diagrams (DFDs)

### 10.2.1 Level 0 DFD (Context Level)
The Level 0 Context Diagram establishes the global boundary of the system, illustrating external entities (Monitored Resident, Optical Camera, Caregivers, System Administrator, SMTP Provider, Database) and their high-level information exchanges.

```
                                  +----------------------+
                                  |    Optical Camera    |
                                  +----------------------+
                                             |
                                             | Raw Video Stream
                                             v
+-----------------------+         +----------------------+         +-----------------------+
|  Monitored Resident   | <=====> |         0.0          | <=====> |  Caregiver Network    |
|  - Touch Responses    |         |    Fall Guard AI     |         |  - Mohini Ravat (C1)  |
|  - Voice Vocalizations|         |    Patient Safety    |         |  - Radha Raghav (C2)  |
|  - Safety Status View |         |    Core Platform     |         |  - Triage Actions     |
+-----------------------+         +----------------------+         +-----------------------+
                                     |       |        |
                       System Config |       |        | Real Email Alerts
                       & Audit Query |       |        v
                                     |       |  +----------------------+
                                     v       |  |  SMTP Mail Provider  |
               +-----------------------+     |  +----------------------+
               | System Administrator  |     |
               +-----------------------+     v
                                        +----------------------+
                                        |   MongoDB / JSON     |
                                        |   Incident Store     |
                                        +----------------------+
```

### 10.2.2 Level 1 DFD (Process Decomposition)
The Level 1 Diagram breaks down the system into five primary sub-processes:
1. `Process 1.0`: Frame Acquisition & Landmark Extraction
2. `Process 2.0`: Kinematic Feature Calculation
3. `Process 3.0`: Temporal Fall Classification & Evidence Synthesis
4. `Process 4.0`: 5-State Emergency Verification Management
5. `Process 5.0`: Tiered Escalation Routing & Incident Auditing

```
[ Camera ]
   |
   | (Video Frames)
   v
+------------------------------------+
| 1.0 Frame Acquisition & Pose Est.  |
+------------------------------------+
   |
   | (33 Topological Landmarks: P0 - P32)
   v
+------------------------------------+
| 2.0 Kinematic Feature Calculation  | <==== [ User Sensitivity Config ]
+------------------------------------+
   |
   | (Torso Angle θ, Velocity v_ΔY, Aspect Ratio Φ)
   v
+------------------------------------+
| 3.0 Temporal Motion Classification |
+------------------------------------+
   |                                 \
   | (Normal ADL: Stand, Sit, Bend)   \ (Possible Fall Trigger)
   v                                   v
[ Real-Time Display ]       +------------------------------------+
                            | 4.0 5-State Verification Loop      | <==== [ Resident Response ]
                            +------------------------------------+       (Touch / Voice)
                               |                                 \
                               | (User says "I'M OK")             \ (Timeout / "NEED HELP")
                               v                                   v
                     [ Resolve Safe ]            +------------------------------------+
                                                 | 5.0 Tiered Caretaker Escalation    |
                                                 +------------------------------------+
                                                    |                |              |
                                                    v                v              v
                                                [ Mohini ]       [ Radha ]      [ Admin ]
                                                    |                |              |
                                                    +----------------+--------------+
                                                                     |
                                                                     v
                                                            [ MongoDB / JSON Store ]
```

### 10.2.3 Level 2 DFD (Decomposition of Process 3.0 & 4.0)
This Level 2 decomposition details the sub-processes within the Temporal Decision and Verification engine:

```
               (Torso Angle θ, Velocity v_ΔY, Aspect Ratio Φ)
                                     |
                                     v
                 +---------------------------------------+
                 | 3.1 Velocity Spike Analysis           |
                 |     Is v_ΔY ≥ 0.035 units/frame?      |
                 +---------------------------------------+
                        /                         \
                (YES)  /                           \ (NO)
                      v                             v
+---------------------------------------+   +---------------------------------------+
| 3.2 Postural Persistence Evaluator    |   | 3.4 ADL Categorizer                   |
|     Is θ ≥ 38° for N ≥ 3 frames?      |   |     Map to: Sitting, Bending, Walking |
+---------------------------------------+   +---------------------------------------+
         /                     \                            |
 (YES)  /                       \ (NO)                      v
       v                         v                [ Update Telemetry Normal ]
+----------------------------+  +----------------------------+
| 3.3 Flag "Possible Fall"   |  | 3.5 Bed Resting Evaluator  |
|     Synthesize Evidence    |  |     v < 0.018 ➔ Suppress   |
+----------------------------+  +----------------------------+
       |
       v
+-------------------------------------------------------+
| 4.1 Initialize State Machine (SUSPECTED_FALL)         |
+-------------------------------------------------------+
       |
       v
+-------------------------------------------------------+
| 4.2 Start 15-Second Verification Countdown Timer      |
+-------------------------------------------------------+
       |                                   \
       | (Touch "I'M OK" / Voice "OK")      \ (Timeout / Touch "NEED HELP")
       v                                     v
+----------------------------+       +---------------------------------------+
| 4.3 State: RESOLVED_SAFE   |       | 4.4 State: ESCALATE_CARETAKERS        |
+----------------------------+       +---------------------------------------+
```

## 10.3 UML Diagrams

### 10.3.1 Use Case Diagram
The Use Case Diagram defines the interactions between the system actors (**Resident**, **System Administrator**, **Caretaker 1: Mohini Ravat**, and **Caretaker 2: Radha Raghav**) and system use cases.

```
                          +-------------------------------------------------------------+
                          |                   FALL GUARD AI USE CASES                   |
                          +-------------------------------------------------------------+

      (Resident) ----------> [ UC-01: View Safety Status Banner ]
           |---------------> [ UC-02: Trigger One-Touch Emergency SOS ]
           |---------------> [ UC-03: Respond to Emergency Verification (I'M OK / HELP) ]
           |---------------> [ UC-04: Issue Hands-Free Voice Commands ]
           |---------------> [ UC-05: Toggle Privacy Ghost Mode Avatar ]
           
    (Mohini Ravat) --------> [ UC-06: Toggle Caretaker 1 On-Duty Status ]
   (Caretaker 1) ----------> [ UC-07: Receive & Triage Assigned Fall Incident ]
           |---------------> [ UC-08: Confirm "I Am Attending to Patient" ]
           |---------------> [ UC-09: Forward Emergency to Radha Raghav (Caretaker 2) ]
           |---------------> [ UC-10: View Live Patient Room Video Stream ]
           
    (Radha Raghav) --------> [ UC-11: Toggle Caretaker 2 Backup Standby Status ]
   (Caretaker 2) ----------> [ UC-12: Monitor Primary Caretaker Watch Status ]
           |---------------> [ UC-13: Receive Escalated Failover Incident Alert ]
           |---------------> [ UC-14: Confirm "I Am Attending to Patient" ]
           |---------------> [ UC-15: Escalate Alert to System Administrator Override ]
           
    (System Admin) --------> [ UC-16: Monitor Master Multi-Camera Stream ]
           |---------------> [ UC-17: Register & Configure Multi-Room Nodes ]
           |---------------> [ UC-18: Manage Caregiver Roster & Override Status ]
           |---------------> [ UC-19: Inspect Chronological Audit History & Timelines ]
           |---------------> [ UC-20: Tune Biomechanical Sensitivity Parameters ]
           |---------------> [ UC-21: Execute Simulated Tiered Failover Drill ]
```

### 10.3.2 Class Diagram
The Class Diagram documents the static structural architecture of the software, identifying key classes, member attributes, methods, visibility, and dependencies.

```
+---------------------------------------------------------------------------------------------------+
|                                     FALL GUARD AI CLASS DIAGRAM                                   |
+---------------------------------------------------------------------------------------------------+

+---------------------------------------+             +---------------------------------------+
|             PoseDetector              |             |           LandmarkExtractor           |
+---------------------------------------+             +---------------------------------------+
| - mp_pose: mediapipe.solutions.pose   |             | - landmark_names: List[str]           |
| - pose: mp_pose.Pose                  |             +---------------------------------------+
| - _lock: threading.Lock               |             | + extract(results): Dict[str, Any]    |
+---------------------------------------+             | + get_visibility_score(): float       |
| + process_frame(frame): (frame, res)  |             +---------------------------------------+
| + close(): void                       |                                |
+---------------------------------------+                                v
                   |                                  +---------------------------------------+
                   v                                  |           FeatureCalculator           |
+---------------------------------------+             +---------------------------------------+
|          TemporalFallDetector         |             | + calculate(landmarks): Dict[str, Any]|
+---------------------------------------+             | + calculate_torso_angle(): float      |
| - fall_angle_threshold: float         | <---------- | + calculate_aspect_ratio(): float     |
| - drop_velocity_threshold: float      |             | + calculate_centroid(): Tuple[float]  |
| - verification_frames: int            |             +---------------------------------------+
| - history_buffer: List[Dict]          |
+---------------------------------------+
| + update(features, t): Dict[str, Any] |
| + evaluate_posture(): str             |
| + synthesize_evidence(): List[str]    |
+---------------------------------------+
                   |
                   v
+---------------------------------------+             +---------------------------------------+
|         IncidentStateMachine          |             |      CaregiverNotificationService     |
+---------------------------------------+             +---------------------------------------+
| - current_state: str                  |             | - SMTP_HOST: str                      |
| - active_incident_id: str             |             | - SMTP_PORT: int                      |
| - countdown_seconds: int              |             +---------------------------------------+
+---------------------------------------+             | + is_configured(): bool               |
| + create_incident(...): Dict          | ----------> | + dispatch_tiered_escalation(...):Dict|
| + respond_i_am_ok(inc_id, src): void  |             | + dispatch_incident_alert(...): Dict  |
| + respond_need_help(inc_id, src): void|             | + send_test_alert(): Dict             |
| + handle_countdown_timeout(): void    |             +---------------------------------------+
| + transition(inc_id, state, note):void|                                |
+---------------------------------------+                                v
                   |                                  +---------------------------------------+
                   +--------------------------------> |            DatabaseManager            |
                                                      +---------------------------------------+
                                                      | - client: MongoClient                 |
                                                      | - db: Database                        |
                                                      | - is_connected: bool                  |
                                                      | - _local_cache: Dict[str, List]       |
                                                      +---------------------------------------+
                                                      | + find(coll, filter): List[Dict]      |
                                                      | + find_one(coll, query): Dict         |
                                                      | + insert_one(coll, doc): str          |
                                                      | + update_one(coll, q, upd): bool      |
                                                      | + _load_local_data(): void            |
                                                      +---------------------------------------+
```

### 10.3.3 Sequence Diagram
This Sequence Diagram illustrates the temporal message ordering during a fall incident: detection, interactive verification countdown, failover escalation to Caretaker 1, transfer to Caretaker 2, and ultimate resolution.

```
Resident        Camera/Detector       StateMachine       NotificationService    Mohini (C1)     Radha (C2)      Database
   |                   |                    |                     |                  |               |             |
   |--- Sudden Fall -->|                    |                     |                  |               |             |
   |                   |-- Angle>38°,v>0.035|                     |                  |               |             |
   |                   |-- create_incident->|                     |                  |               |             |
   |                   |                    |-- insert_one ------------------------------------------------------->|
   |<-- Alert Prompt --|                    |                     |                  |               |             |
   |    (15s Countdown)|                    |                     |                  |               |             |
   |                   |                    |                     |                  |               |             |
   |   (No Response /  |                    |                     |                  |               |             |
   |    Timer Expires) |                    |                     |                  |               |             |
   |                   |                    |-- timeout_handler ->|                  |               |             |
   |                   |                    |                     |-- dispatch_tier->|               |             |
   |                   |                    |                     |-- Tier 1 Email ->|               |             |
   |                   |                    |                     |   (Mohini Ravat) |==== Alert ===>|             |
   |                   |                    |                     |                  |               |             |
   |                   |                    |                     |                  |-- [Cannot] -->|             |
   |                   |                    |                     |                  |   Forward C2  |             |
   |                   |                    |                     |<-- Failover Call-+               |             |
   |                   |                    |                     |-- Tier 2 Email ----------------->|             |
   |                   |                    |                     |   (Radha Raghav) |== Esc Alert =>|             |
   |                   |                    |                     |                                  |             |
   |                   |                    |                     |                                  |-- Attending |
   |                   |                    |<-- Transition: RESOLVED_CARETAKER_2 -------------------+             |
   |                   |                    |-- update_one: Status & Timeline ------------------------------------>|
   |<-- "Help Arriving"|                    |                                                                      |
```

### 10.3.4 Activity Diagram
The Activity Diagram models the complete business workflow from initialization and video processing through to incident closure.

```
       (*) Start System
            |
            v
   [ Ingest Video Frame ]
            |
            v
   < Person Detected by MediaPipe? >
         /                 \
       (No)               (Yes)
        /                   \
[ Display Searching ]   [ Calculate Torso Angle θ & Velocity v_ΔY ]
        \                   /
         \                 v
   < Is Drop Velocity v_ΔY ≥ 0.035 AND Torso Angle θ ≥ 38°? >
               /                                      \
             (No)                                    (Yes)
              /                                        \
     [ Classify ADL ]                        [ Generate Incident ID in MongoDB ]
  (Stand, Sit, Bend, Bed)                              |
              |                                        v
  [ Render Normal UI ]                       [ Launch 15-Second Verification Dialog ]
              |                                        |
              |                              < Resident Response? >
              |                             /          |           \
              |                     ("I'M OK")   ("NEED HELP")   (Timeout 0s)
              |                        /               \           /
              |                       v                 v         v
              |               [ Mark Resolved ]    [ Trigger Tiered Escalation ]
              |                       |                         |
              |                       |            < Caretaker 1 (Mohini) Available? >
              |                       |                 /                  \
              |                       |               (Yes)                (No)
              |                       |                /                     \
              |                       |       [ Alert Mohini ]      < Caretaker 2 (Radha) Avail? >
              |                       |                |                 /                \
              |                       |                |               (Yes)              (No)
              |                       |                |                /                   \
              |                       |                |       [ Alert Radha ]       [ Admin Override ]
              |                       |                |                |                   |
              |                       |                +----------------+-------------------+
              |                       |                                 |
              |                       v                                 v
              +-----------------> [ Log Audit Trail in MongoDB / Local JSON ]
                                      |
                                      v
                                  (*) Repeat Continuous Loop
```

### 10.3.5 State Machine Diagram (5-State Lifecycle)
The State Machine Diagram formalizes the five discrete states governing emergency incident management:

```
                      +-----------------------------+
                      |         1. NORMAL           |
                      |   (Continuous Tracking)     |
                      +-----------------------------+
                                     |
                                     | Event: Fall Detected (θ ≥ 38°, v ≥ 0.035, N ≥ 3)
                                     v
                      +-----------------------------+
                      |      2. SUSPECTED_FALL      |
                      |   (Capture Frame & Metrics) |
                      +-----------------------------+
                                     |
                                     | Action: Initialize 15s Timer
                                     v
                      +-----------------------------+
                      |   3. PENDING_VERIFICATION   |
                      |   (Modal Prompt Active)     |
                      +-----------------------------+
                         /           |             \
       Action: "I'M OK" /            |              \ Action: Timeout (0s) OR
       Voice: "I'm okay"             |               \         Button: "I NEED HELP"
                       /             |                \
                      v              |                 v
+-----------------------------+      |      +-----------------------------+
|      4. RESOLVED_SAFE       |      |      |   5. ESCALATED_DISPATCH     |
|   (False Alarm Suppressed)  |      |      |   (Tier 1 ➔ Tier 2 ➔ Admin) |
+-----------------------------+      |      +-----------------------------+
              |                      |                     |
              |                      |                     | Action: Caretaker Acknowledges Safe
              |                      |                     v
              |                      |      +-----------------------------+
              +----------------------+----> |         6. CLOSED           |
                                            |   (Archived to MongoDB)     |
                                            +-----------------------------+
```

## 10.4 Database Diagram (Entity-Relationship ER Diagram)
The database architecture employs five document collections managed via MongoDB with schema validation:

```
+----------------------------------+                   +----------------------------------+
|            incidents             |                   |            caregivers            |
+----------------------------------+                   +----------------------------------+
| PK  incident_id        (String)  |                   | PK  email              (String)  |
| FK  camera_id          (String)  |                   |     name               (String)  |
|     room_id            (String)  |                   |     role               (String)  |
|     detected_at        (ISODate) |                   |     phone              (String)  |
|     body_angle_degrees (Double)  |                   |     priority           (Integer) |
|     status             (String)  |                   |     is_active          (Boolean) |
|     user_response      (String)  |                   |     is_available       (Boolean) |
|     notification_status(String)  |                   |     username           (String)  |
|     detection_evidence (Array)   |                   |     preferred_method   (String)  |
|     escalation_chain   (Array)   |                   +----------------------------------+
|     timeline           (Array)   |                                     |
+----------------------------------+                                     |
                 |                                                       |
                 | (1 : N)                                               | (1 : N)
                 v                                                       v
+----------------------------------+                   +----------------------------------+
|             cameras              |                   |        evaluation_trials         |
+----------------------------------+                   +----------------------------------+
| PK  camera_id          (String)  |                   | PK  trial_id           (String)  |
|     room_name          (String)  |                   |     activity_category  (String)  |
|     hardware_index     (Integer) |                   |     ground_truth       (String)  |
|     resolution         (String)  |                   |     predicted_posture  (String)  |
|     status             (String)  |                   |     classification_correct(Bool) |
|     location_type      (String)  |                   |     execution_timestamp(ISODate) |
+----------------------------------+                   +----------------------------------+
```

## 10.5 Table Structure / Document Schema

### 10.5.1 Schema for `incidents` Collection
The `incidents` collection serves as the central audit store for all detected events, state machine transitions, and notifications.

```
+--------------------+--------------+----------+--------------------------------------------------------+
| Field Name         | BSON Type    | Nullable | Description & Constraints                              |
+--------------------+--------------+----------+--------------------------------------------------------+
| _id                | ObjectId     | False    | Default unique MongoDB primary object identifier.       |
| incident_id        | String       | False    | Unique business key (e.g., "INC-20261013-143022").     |
| camera_id          | String       | False    | Foreign reference to originating camera node.          |
| room_id            | String       | False    | Location tag (e.g., "Living Room — Camera 1").         |
| detected_at        | String (ISO) | False    | Timestamp of initial fall detection event.             |
| body_angle_degrees | Double       | False    | Computed torso inclination from vertical (degrees).    |
| status             | String       | False    | State: "NORMAL", "SUSPECTED", "RESOLVED", "ESCALATED". |
| user_response      | String       | False    | "NONE", "IM_OK", "NEED_HELP", "VOICE_OK".              |
| notification_status| String       | False    | "SENT", "FAILED", "NOT_CONFIGURED", "ESCALATED_ADMIN".  |
| detection_evidence | Array[String]| False    | Synthesized biomechanical observation bullet points.   |
| escalation_chain   | Array[Object]| False    | Tiered dispatch audit trail [{tier, name, status}].    |
| timeline           | Array[Object]| False    | Chronological event log [{time: "HH:MM:SS", event}].   |
+--------------------+--------------+----------+--------------------------------------------------------+
```

### 10.5.2 Schema for `caregivers` Collection
Manages primary, secondary, and administrative caregivers, contact information, and duty states.

```
+--------------------+--------------+----------+--------------------------------------------------------+
| Field Name         | BSON Type    | Nullable | Description & Constraints                              |
+--------------------+--------------+----------+--------------------------------------------------------+
| _id                | ObjectId     | False    | Default unique MongoDB primary object identifier.       |
| name               | String       | False    | Full legal name (e.g., "Mohini Ravat").                |
| email              | String       | False    | Unique email address used for SMTP alert routing.      |
| role               | String       | False    | Professional designation (e.g., "Primary Caretaker").  |
| phone              | String       | False    | Contact telephone with country code (+91).             |
| priority           | Integer      | False    | Dispatch tier: 1 (Primary), 2 (Secondary), 3 (Admin).  |
| is_active          | Boolean      | False    | Account enablement status (True/False).                |
| is_available       | Boolean      | False    | Real-time on-duty status controlling automated failover|
| username           | String       | False    | Unique login credential username.                      |
| preferred_method   | String       | False    | Preferred alert modality: "EMAIL", "SMS", "ALL".       |
+--------------------+--------------+----------+--------------------------------------------------------+
```

### 10.5.3 Schema for `cameras` Collection
```
+--------------------+--------------+----------+--------------------------------------------------------+
| Field Name         | BSON Type    | Nullable | Description & Constraints                              |
+--------------------+--------------+----------+--------------------------------------------------------+
| camera_id          | String       | False    | Unique hardware camera identifier (e.g., "CAM-001").   |
| room_name          | String       | False    | Human-readable room label (e.g., "Living Room").       |
| hardware_index     | Integer      | False    | DirectShow device enumeration index (0, 1, 2).         |
| resolution         | String       | False    | Capture resolution (e.g., "640x480").                  |
| status             | String       | False    | Operational status: "ONLINE", "STANDBY", "OFFLINE".    |
| location_type      | String       | False    | Zone categorization: "Common Area", "High-Risk Recovery|
+--------------------+--------------+----------+--------------------------------------------------------+
```

### 10.5.4 Schema for `evaluation_trials` Collection
```
+----------------------+--------------+----------+------------------------------------------------------+
| Field Name           | BSON Type    | Nullable | Description & Constraints                            |
+----------------------+--------------+----------+------------------------------------------------------+
| trial_id             | String       | False    | Unique empirical test run identifier.                |
| activity_category    | String       | False    | Category: "Fall", "Standing", "Bending", "Sitting".  |
| ground_truth         | String       | False    | Verified ground-truth action label.                  |
| predicted_posture    | String       | False    | Posture label output by temporal kinematic detector. |
| classification_correct Boolean     | False    | Binary evaluation outcome (True = Match).            |
| execution_timestamp  | String (ISO) | False    | Timestamp of benchmark execution.                    |
+----------------------+--------------+----------+------------------------------------------------------+
```
""")
    print("Chapters 9 and 10 appended.")

if __name__ == "__main__":
    append_section_9_10()
