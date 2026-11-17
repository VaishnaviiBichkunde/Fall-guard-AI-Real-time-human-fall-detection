"""
Reusable Machine Learning Feature Pipeline for Fall Guard AI.
Extracts normalized 12-dimensional feature vectors from MediaPipe pose features.
"""

from typing import Any, Dict, List, Optional
import numpy as np


FEATURE_NAMES = [
    "body_angle_degrees",
    "horizontal_ratio",
    "hip_y",
    "shoulder_to_hip_length",
    "shoulder_width",
    "knee_angle_degrees",
    "delta_x_abs",
    "delta_y_abs",
    "mean_visibility",
    "aspect_ratio_torso",
    "estimated_vertical_drop",
    "kinetic_acceleration",
]


class FeaturePipeline:
    """Transforms raw pose landmarks and biomechanical metrics into structured ML vectors."""

    def extract_vector(
        self,
        features: Optional[Dict[str, Any]],
        velocity: float = 0.0,
        acceleration: float = 0.0,
    ) -> Optional[np.ndarray]:
        if features is None:
            return None

        angle = float(features.get("body_angle_degrees", 0.0))
        ratio = float(features.get("horizontal_ratio", 0.0))
        hip_y = float(features.get("hip_y", 0.5))
        torso_len = float(features.get("shoulder_to_hip_length", 0.3))
        shoulder_w = float(features.get("shoulder_width", 0.2))
        knee_angle = float(features.get("knee_angle_degrees", 180.0))
        dx = abs(float(features.get("delta_x", 0.0)))
        dy = abs(float(features.get("delta_y", 0.3)))
        vis = float(features.get("mean_visibility", 1.0))
        aspect = shoulder_w / (torso_len + 1e-5)

        vector = np.array(
            [
                angle,
                min(ratio, 10.0),
                hip_y,
                torso_len,
                shoulder_w,
                knee_angle,
                dx,
                dy,
                vis,
                aspect,
                velocity,
                acceleration,
            ],
            dtype=np.float32,
        )
        return vector

    def get_feature_names(self) -> List[str]:
        return FEATURE_NAMES
