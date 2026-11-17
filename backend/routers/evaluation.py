"""
FastAPI Router for Scientific Evaluation & Model Benchmarks.
"""

from typing import Any, Dict, List
from fastapi import APIRouter
from backend.models import EvaluationTrialLog
from core.evaluation_engine import EvaluationEngine

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("/metrics")
def get_evaluation_metrics():
    """Compute and return binary confusion matrix, accuracy, precision, recall, specificity, F1-score."""
    return EvaluationEngine.calculate_binary_metrics()


@router.get("/comparison")
def get_detector_comparison():
    """Retrieve side-by-side performance comparison of the 3 detectors."""
    return EvaluationEngine.get_detector_comparison()


@router.get("/trials")
def get_trials():
    """Retrieve all evaluation benchmark trials."""
    return EvaluationEngine.get_all_trials()


@router.post("/trials")
def log_trial(trial: EvaluationTrialLog):
    """Log an individual evaluation trial."""
    doc = EvaluationEngine.record_trial(
        trial_id=trial.trial_id,
        activity_category=trial.activity_category,
        ground_truth_label=trial.ground_truth_label,
        predicted_label=trial.predicted_label,
        alert_raised=trial.alert_raised,
        detection_latency_seconds=trial.detection_latency_seconds,
    )
    return doc
