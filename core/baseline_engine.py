"""
Personalized Activity Baseline & Calibration Engine for Fall Guard AI.
Records user-specific movement profiles and computes statistical deviation metrics.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import numpy as np

from backend.database import db_manager


class BaselineEngine:
    """Manages recording and statistical evaluation of user movement baselines."""

    @staticmethod
    def get_baseline(user_id: str = "primary_user") -> Optional[Dict[str, Any]]:
        """Retrieves stored baseline profile for user."""
        return db_manager.find_one("user_baselines", {"user_id": user_id})

    @staticmethod
    def save_baseline(
        user_id: str,
        observations: List[Dict[str, Any]],
        label: str = "Default Baseline Profile",
    ) -> Dict[str, Any]:
        """
        Computes descriptive statistics across labelled calibration observations
        and saves the baseline metadata to MongoDB.
        """
        if not observations:
            raise ValueError("No calibration observations provided.")

        angles = [obs.get("body_angle_degrees", 0.0) for obs in observations]
        velocities = [obs.get("velocity", 0.0) for obs in observations]
        hip_heights = [obs.get("hip_y", 0.5) for obs in observations]

        doc = {
            "user_id": user_id,
            "label": label,
            "sample_count": len(observations),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "angle_stats": {
                "mean": round(float(np.mean(angles)), 2),
                "std": round(float(np.std(angles)), 2),
                "min": round(float(np.min(angles)), 2),
                "max": round(float(np.max(angles)), 2),
                "p95": round(float(np.percentile(angles, 95)), 2),
            },
            "velocity_stats": {
                "mean": round(float(np.mean(velocities)), 4),
                "std": round(float(np.std(velocities)), 4),
                "max": round(float(np.max(velocities)), 4),
            },
            "hip_stats": {
                "mean": round(float(np.mean(hip_heights)), 3),
                "std": round(float(np.std(hip_heights)), 3),
            },
        }

        db_manager.insert_one("user_baselines", doc)
        return doc

    @staticmethod
    def evaluate_deviation(
        current_features: Dict[str, Any],
        user_id: str = "primary_user",
    ) -> Dict[str, Any]:
        """
        Evaluates how far current posture deviates from personal baseline.
        Returns z-scores and context signals.
        """
        baseline = BaselineEngine.get_baseline(user_id)
        if not baseline:
            return {
                "has_baseline": False,
                "deviation_score": 0.0,
                "status": "DEFAULT THRESHOLDS ACTIVE",
                "message": "No calibrated baseline. Using standard safety thresholds.",
            }

        angle_mean = baseline["angle_stats"]["mean"]
        angle_std = max(1.0, baseline["angle_stats"]["std"])
        curr_angle = current_features.get("body_angle_degrees", 0.0)

        # Calculate Z-score distance
        z_score = abs(curr_angle - angle_mean) / angle_std

        return {
            "has_baseline": True,
            "deviation_score": round(float(z_score), 2),
            "baseline_mean_angle": angle_mean,
            "status": "EVALUATING WITH PERSONAL CONTEXT",
            "message": f"Torso angle deviation: {z_score:.1f}σ from personal baseline ({angle_mean:.1f}°).",
        }

    @staticmethod
    def reset_baseline(user_id: str = "primary_user") -> bool:
        """Deletes user baseline profile."""
        db_manager.delete_many("user_baselines", {"user_id": user_id})
        return True
