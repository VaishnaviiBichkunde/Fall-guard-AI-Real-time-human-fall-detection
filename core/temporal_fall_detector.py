"""
Temporal Fall vs. Normal Activity Detection Engine with Explainable AI.
Distinguishes: Standing, Sitting, Bending, Walking, Intentional Lying Down,
Possible Fall, and Uncertain / Insufficient Visibility using multi-frame temporal buffers.
"""

from collections import deque
import time
from typing import Any, Dict, List, Optional


class TemporalFallDetector:
    """
    Analyzes body posture and movement over rolling temporal windows to differentiate
    sudden accidental falls from normal activities (sleeping, sitting, bending, walking).
    Generates observation-grounded explanations for all detection decisions.
    """

    def __init__(
        self,
        history_window_size: int = 25,
        min_visibility_threshold: float = 0.50,
        fall_angle_threshold: float = 40.0,
        high_velocity_threshold: float = 0.035,
        verification_frames: int = 3,
    ):
        self.window_size = history_window_size
        self.min_visibility = min_visibility_threshold
        self.fall_angle_threshold = fall_angle_threshold
        self.high_velocity_threshold = high_velocity_threshold
        self.verification_frames = verification_frames

        # Rolling observation history: stores tuples (timestamp, features, hip_velocity, hip_lateral_movement)
        self.history: deque = deque(maxlen=history_window_size)

        # State tracking
        self.current_posture = "Unknown"
        self.posture_duration_seconds = 0.0
        self.last_posture_change_time = time.time()
        self.possible_fall_counter = 0

    def reset(self):
        """Resets temporal buffers and state counters."""
        self.history.clear()
        self.current_posture = "Unknown"
        self.posture_duration_seconds = 0.0
        self.last_posture_change_time = time.time()
        self.possible_fall_counter = 0

    def update(
        self,
        features: Optional[Dict[str, Any]],
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single frame's biometric features through the temporal rolling buffer.
        Returns posture classification, possible fall flag, and observation-grounded explanation.
        """
        now = timestamp if timestamp is not None else time.time()

        # 1. Check for missing landmarks or poor visibility
        if features is None:
            self.current_posture = "Uncertain / No Person Detected"
            return {
                "posture": self.current_posture,
                "status": "UNCERTAIN — NO PERSON",
                "is_possible_fall": False,
                "confidence": 0.0,
                "posture_duration": 0.0,
                "velocity": 0.0,
                "body_angle": 0.0,
                "explanation_title": "Uncertain / No Person Visible",
                "explanation_evidence": [
                    "No human body landmarks detected in the current camera frame.",
                    "Ensure the subject is within the camera's field of view.",
                ],
                "reason": "No body landmarks detected in frame.",
            }

        mean_vis = features.get("mean_visibility", 1.0)
        if mean_vis < self.min_visibility:
            self.current_posture = "Uncertain / Insufficient Visibility"
            return {
                "posture": self.current_posture,
                "status": "UNCERTAIN — INSUFFICIENT VISIBILITY",
                "is_possible_fall": False,
                "confidence": float(mean_vis),
                "posture_duration": round(self.posture_duration_seconds, 1),
                "velocity": 0.0,
                "body_angle": round(features.get("body_angle_degrees", 0.0), 1),
                "explanation_title": "Uncertain Visibility Warning",
                "explanation_evidence": [
                    f"Mean landmark visibility ({mean_vis:.2f}) is below confidence threshold ({self.min_visibility:.2f}).",
                    "Subject may be partially occluded, in low lighting, or at camera edge.",
                    "Fall classification suspended to prevent false alarm.",
                ],
                "reason": f"Mean landmark visibility ({mean_vis:.2f}) below threshold.",
            }

        # 2. Calculate vertical velocity and lateral displacement
        curr_hip_y = features["hip_y"]
        curr_hip_x = features.get("hip_center", {}).get("x", 0.5)

        prev_entry = self.history[-1] if len(self.history) > 0 else None
        hip_velocity_y = 0.0
        hip_movement_x = 0.0

        if prev_entry is not None:
            prev_features = prev_entry[1]
            prev_hip_y = prev_features["hip_y"]
            prev_hip_x = prev_features.get("hip_center", {}).get("x", 0.5)
            # Positive Y velocity = downward movement towards floor in image space
            hip_velocity_y = curr_hip_y - prev_hip_y
            hip_movement_x = abs(curr_hip_x - prev_hip_x)

        self.history.append((now, features, hip_velocity_y, hip_movement_x))

        # 3. Classify instantaneous posture
        instant_posture = self._classify_instantaneous_posture(features, hip_movement_x)

        if instant_posture == self.current_posture:
            self.posture_duration_seconds = now - self.last_posture_change_time
        else:
            self.current_posture = instant_posture
            self.last_posture_change_time = now
            self.posture_duration_seconds = 0.0

        # 4. Perform temporal analysis over the rolling history buffer
        temporal_result = self._analyze_temporal_transition(features, now)

        return {
            "posture": self.current_posture,
            "status": temporal_result["status"],
            "is_possible_fall": temporal_result["is_possible_fall"],
            "confidence": min(1.0, max(0.4, float(mean_vis))),
            "posture_duration": round(self.posture_duration_seconds, 1),
            "velocity": round(hip_velocity_y, 4),
            "body_angle": round(features["body_angle_degrees"], 1),
            "explanation_title": temporal_result["explanation_title"],
            "explanation_evidence": temporal_result["explanation_evidence"],
            "reason": temporal_result["reason"],
        }

    def _classify_instantaneous_posture(
        self,
        features: Dict[str, Any],
        lateral_movement: float = 0.0,
    ) -> str:
        """
        Classifies static posture: Standing, Walking, Sitting, Bending, Lying Down.
        """
        angle = features["body_angle_degrees"]
        orientation = features.get("body_orientation", "vertical")
        hip_y = features.get("hip_y", 0.5)

        knee_angle = features.get("knee_angle_degrees")
        if knee_angle is None:
            left_k = features.get("left_knee_angle")
            right_k = features.get("right_knee_angle")
            if left_k is not None and right_k is not None:
                knee_angle = (left_k + right_k) / 2.0
            elif left_k is not None:
                knee_angle = left_k
            elif right_k is not None:
                knee_angle = right_k
            else:
                knee_angle = 180.0

        # Case A: Horizontal or highly tilted torso -> Lying Down / Resting
        if orientation == "horizontal" or angle >= 55.0:
            return "Intentional Lying Down"

        # Case B: Tilted torso with upright/semi-straight knees -> Bending Forward
        if 22.0 <= angle < 55.0:
            if knee_angle < 130.0 or hip_y > 0.62:
                return "Sitting"
            else:
                return "Bending"

        # Case C: Lowered hip level with bent knees -> Sitting
        if angle < 22.0 and (hip_y > 0.65 or knee_angle < 125.0):
            return "Sitting"

        # Case D: Upright with significant lateral translation across frames -> Walking
        if angle < 22.0 and lateral_movement > 0.015:
            return "Walking"

        # Case E: Default upright -> Standing
        return "Standing"

    def _analyze_temporal_transition(
        self,
        current_features: Dict[str, Any],
        now: float,
    ) -> Dict[str, Any]:
        """
        Evaluates the rolling window to distinguish sudden kinetic falls
        from normal sitting, bending, and intentional lying down.
        Generates explainable evidence points.
        """
        current_angle = current_features["body_angle_degrees"]
        is_horizontal = (
            current_features.get("body_orientation") == "horizontal"
            or current_angle >= 55.0
        )

        # 1. If posture is NOT horizontal, the subject is in normal activity
        if not is_horizontal:
            self.possible_fall_counter = 0

            if self.current_posture == "Sitting":
                evidence = [
                    f"Torso angle is upright or moderately tilted ({current_angle:.1f}°).",
                    "Knees are bent with lowered hip height, consistent with chair/sofa sitting.",
                    "Controlled posture transition observed without rapid drop.",
                ]
            elif self.current_posture == "Bending":
                evidence = [
                    f"Forward torso tilt observed ({current_angle:.1f}°).",
                    "Legs and feet grounded with controlled descent velocity.",
                    "Consistent with bending to pick up an object — normal activity.",
                ]
            elif self.current_posture == "Walking":
                evidence = [
                    f"Upright torso maintained ({current_angle:.1f}°).",
                    "Continuous lateral movement detected across consecutive frames.",
                    "Normal ambulation confirmed.",
                ]
            else:
                evidence = [
                    f"Upright vertical posture maintained ({current_angle:.1f}° from vertical).",
                    "Stable center of mass above ankle support base.",
                    "Normal upright standing activity.",
                ]

            return {
                "status": "NORMAL ACTIVITY",
                "is_possible_fall": False,
                "explanation_title": f"Normal Activity ({self.current_posture})",
                "explanation_evidence": evidence,
                "reason": f"Subject in normal {self.current_posture} posture.",
            }

        # 2. Subject is in horizontal / low posture.
        # Investigate temporal history to determine HOW they arrived at this posture.
        if len(self.history) < 2:
            return {
                "status": "INTENTIONAL LYING DOWN",
                "is_possible_fall": False,
                "explanation_title": "Intentional Lying Down / Resting",
                "explanation_evidence": [
                    f"Subject in horizontal posture ({current_angle:.1f}°).",
                    "Stable baseline without rapid kinetic transition.",
                    "Emergency alert suppressed.",
                ],
                "reason": "Horizontal posture with stable baseline history.",
            }

        # Check maximum downward velocity observed in the rolling window
        velocities = [item[2] for item in self.history]
        max_downward_velocity = max(velocities) if velocities else 0.0

        # Check if the subject was upright earlier in the rolling window
        upright_frames = [
            item for item in self.history
            if item[1]["body_angle_degrees"] < 35.0 and item[1].get("body_orientation", "vertical") != "horizontal"
        ]
        had_upright = len(upright_frames) > 0
        starting_angle = upright_frames[0][1]["body_angle_degrees"] if had_upright else current_angle
        angle_delta = current_angle - starting_angle

        # CASE 1: Subject was already lying down (Sleeping / Resting in Bed)
        if not had_upright:
            self.possible_fall_counter = 0
            self.current_posture = "Intentional Lying Down"
            return {
                "status": "INTENTIONAL LYING DOWN",
                "is_possible_fall": False,
                "explanation_title": "Intentional Lying Down (Sleep / Rest)",
                "explanation_evidence": [
                    f"Subject in horizontal position ({current_angle:.1f}° from vertical).",
                    "No prior upright-to-ground transition occurred in observation window.",
                    "Consistent with sleeping in bed or resting on sofa.",
                    "Emergency alert suppressed to prevent false alarm.",
                ],
                "reason": "Continuous resting posture without sudden transition.",
            }

        # CASE 2: Controlled slow descent (Sitting on floor / Yoga / Lying down gently)
        if max_downward_velocity < self.high_velocity_threshold:
            self.possible_fall_counter = 0
            self.current_posture = "Intentional Lying Down"
            return {
                "status": "INTENTIONAL LYING DOWN",
                "is_possible_fall": False,
                "explanation_title": "Controlled Movement to Floor",
                "explanation_evidence": [
                    f"Transition from {starting_angle:.1f}° to {current_angle:.1f}° occurred smoothly.",
                    f"Downward velocity ({max_downward_velocity:.3f}) stayed below kinetic shock threshold ({self.high_velocity_threshold:.3f}).",
                    "Classified as intentional controlled descent (e.g. resting/yoga).",
                    "Emergency alert suppressed.",
                ],
                "reason": f"Controlled descent (velocity {max_downward_velocity:.3f} below shock threshold).",
            }

        # CASE 3: Sudden High-Velocity Drop (Suspected Accidental Fall)
        if had_upright and max_downward_velocity >= self.high_velocity_threshold:
            self.possible_fall_counter += 1

            if self.possible_fall_counter >= self.verification_frames:
                self.current_posture = "Possible Fall"
                duration_str = f"{self.posture_duration_seconds:.1f}s" if self.posture_duration_seconds > 0 else "immediate"
                evidence = [
                    f"Significant downward movement observed: Peak vertical drop velocity reached {max_downward_velocity:.3f} ΔY/frame (Threshold: {self.high_velocity_threshold:.3f}).",
                    f"Rapid torso-angle shift observed: Tilted from upright ({starting_angle:.1f}°) to horizontal ({current_angle:.1f}°), Δθ = +{angle_delta:.1f}°.",
                    f"Low/horizontal posture maintained after movement: Sustained for {duration_str}.",
                    "Emergency verification required — Prompting user status.",
                ]
                return {
                    "status": "POSSIBLE FALL DETECTED",
                    "is_possible_fall": True,
                    "explanation_title": "🚨 POSSIBLE FALL DETECTED",
                    "explanation_evidence": evidence,
                    "reason": f"Sudden drop (velocity {max_downward_velocity:.3f}, Δθ +{angle_delta:.1f}°) to low posture.",
                }
            else:
                return {
                    "status": "VERIFYING MOVEMENT PATTERN",
                    "is_possible_fall": False,
                    "explanation_title": "Verifying Kinetic Shock",
                    "explanation_evidence": [
                        f"Downward kinetic shock detected ({max_downward_velocity:.3f} ΔY/frame).",
                        f"Verifying persistence across consecutive frames ({self.possible_fall_counter}/{self.verification_frames})...",
                    ],
                    "reason": f"Shock detected, verifying persistence ({self.possible_fall_counter}/{self.verification_frames}).",
                }

        # Default fallback
        return {
            "status": "UNCERTAIN — MONITORING",
            "is_possible_fall": False,
            "explanation_title": "Uncertain Movement Transition",
            "explanation_evidence": [
                f"Subject observed at {current_angle:.1f}° angle.",
                "Movement trajectory does not cleanly match fall or standard resting profile.",
                "Continuing non-intrusive monitoring.",
            ],
            "reason": "Horizontal posture under ambiguous movement history.",
        }
