import math
from typing import Any, Dict, Optional


class FeatureCalculator:
    """
    Biomechanical feature extraction from MediaPipe pose landmarks.
    Computes normalized joint centers, torso angles, aspect ratios,
    normalized hip height, joint angles, and visibility scores.
    """

    def calculate(self, landmarks: Optional[Dict[str, Dict[str, float]]]) -> Optional[Dict[str, Any]]:
        if not landmarks:
            return None

        # Check required core landmarks
        required = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]
        if not all(k in landmarks for k in required):
            return None

        shoulder_center = self._center(
            landmarks["left_shoulder"],
            landmarks["right_shoulder"],
        )
        hip_center = self._center(
            landmarks["left_hip"],
            landmarks["right_hip"],
        )

        delta_x = shoulder_center["x"] - hip_center["x"]
        delta_y = shoulder_center["y"] - hip_center["y"]
        shoulder_to_hip_length = math.hypot(delta_x, delta_y)
        shoulder_width = self._distance(
            landmarks["left_shoulder"],
            landmarks["right_shoulder"],
        )

        # Torso angle relative to vertical axis (0° = standing, 90° = horizontal)
        body_angle_degrees = math.degrees(
            math.atan2(abs(delta_x), abs(delta_y) + 1e-6)
        )

        # Ratio of horizontal displacement to vertical displacement
        horizontal_ratio = (
            abs(delta_x) / abs(delta_y)
            if abs(delta_y) > 1e-4
            else float("inf")
        )

        body_orientation = (
            "horizontal" if (horizontal_ratio >= 0.8 or body_angle_degrees >= 40.0) else "vertical"
        )

        # Average visibility of key landmarks
        visibilities = [
            landmarks[k].get("visibility", 1.0)
            for k in required
            if "visibility" in landmarks[k]
        ]
        mean_visibility = sum(visibilities) / len(visibilities) if visibilities else 1.0

        # Normalized hip height (in normalized camera coordinates, y=0 top, y=1 bottom)
        hip_y = hip_center["y"]

        # Knee and ankle calculations if available
        knee_center = None
        ankle_center = None
        knee_angle_degrees = 180.0

        if "left_knee" in landmarks and "right_knee" in landmarks:
            knee_center = self._center(landmarks["left_knee"], landmarks["right_knee"])

        if "left_ankle" in landmarks and "right_ankle" in landmarks:
            ankle_center = self._center(landmarks["left_ankle"], landmarks["right_ankle"])

        # Estimate knee bend angle (hip -> knee -> ankle) if leg landmarks present
        if knee_center and ankle_center:
            v_hip_knee = (knee_center["x"] - hip_center["x"], knee_center["y"] - hip_center["y"])
            v_knee_ankle = (ankle_center["x"] - knee_center["x"], ankle_center["y"] - knee_center["y"])
            dot = v_hip_knee[0] * v_knee_ankle[0] + v_hip_knee[1] * v_knee_ankle[1]
            mag1 = math.hypot(v_hip_knee[0], v_hip_knee[1]) + 1e-6
            mag2 = math.hypot(v_knee_ankle[0], v_knee_ankle[1]) + 1e-6
            cos_val = max(-1.0, min(1.0, dot / (mag1 * mag2)))
            knee_angle_degrees = math.degrees(math.acos(cos_val))

        return {
            "shoulder_center": shoulder_center,
            "hip_center": hip_center,
            "knee_center": knee_center,
            "ankle_center": ankle_center,
            "body_angle_degrees": body_angle_degrees,
            "hip_y": hip_y,
            "shoulder_width": shoulder_width,
            "shoulder_to_hip_length": shoulder_to_hip_length,
            "horizontal_ratio": horizontal_ratio,
            "body_orientation": body_orientation,
            "mean_visibility": mean_visibility,
            "knee_angle_degrees": knee_angle_degrees,
            "delta_x": delta_x,
            "delta_y": delta_y,
        }

    @staticmethod
    def _center(first: Dict[str, float], second: Dict[str, float]) -> Dict[str, float]:
        return {
            "x": (first["x"] + second["x"]) / 2,
            "y": (first["y"] + second["y"]) / 2,
        }

    @staticmethod
    def _distance(first: Dict[str, float], second: Dict[str, float]) -> float:
        return math.hypot(
            first["x"] - second["x"],
            first["y"] - second["y"],
        )
