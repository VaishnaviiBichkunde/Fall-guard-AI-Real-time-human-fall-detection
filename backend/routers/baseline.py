"""
FastAPI Router for Activity Baseline Calibration and Deviation Scoring.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.baseline_engine import BaselineEngine

router = APIRouter(prefix="/api/baseline", tags=["Baseline"])


class CalibrationSessionRequest(BaseModel):
    user_id: str = "primary_user"
    label: str = "Personal Baseline Profile"
    observations: List[Dict[str, Any]]


class ScoreObservationRequest(BaseModel):
    body_angle_degrees: float
    velocity: float
    hip_y: float


@router.get("/{user_id}")
def get_user_baseline(user_id: str = "primary_user"):
    """Get stored baseline stats for a user."""
    baseline = BaselineEngine.get_baseline(user_id)
    if not baseline:
        return {"status": "NO_BASELINE", "message": "No calibrated baseline profile found. Run calibration session."}
    return baseline


@router.post("")
def save_calibration_session(payload: CalibrationSessionRequest):
    """Compute statistics across calibration session and save baseline."""
    if not payload.observations:
        raise HTTPException(status_code=400, detail="Observations list cannot be empty.")
    saved = BaselineEngine.save_baseline(
        user_id=payload.user_id,
        observations=payload.observations,
        label=payload.label,
    )
    return saved


@router.post("/{user_id}/score")
def score_observation(user_id: str, observation: ScoreObservationRequest):
    """Compute baseline deviation score for a single live frame/observation."""
    score_result = BaselineEngine.compute_deviation_score(user_id, observation.model_dump())
    return score_result


@router.post("/{user_id}/reset")
def reset_baseline(user_id: str):
    """Reset user baseline to uncalibrated state."""
    from backend.database import db_manager
    db_manager.delete_one("user_baselines", {"user_id": user_id})
    return {"status": "success", "message": f"Baseline for user {user_id} reset."}
