"""
Unit tests for Scientific Evaluation Module and Confusion Matrix Calculations.
"""

import pytest
from core.evaluation_engine import EvaluationEngine


def test_confusion_matrix_and_metrics_math():
    # Synthetic trial set:
    # 50 TP (fall actual, fall pred)
    # 5 FP (normal actual, fall pred)
    # 2 FN (fall actual, normal pred)
    # 43 TN (normal actual, normal pred)
    # Total = 100 trials
    trials = []
    for i in range(50):
        trials.append({"ground_truth_label": "Fall", "predicted_label": "Fall", "alert_raised": True, "detection_latency_seconds": 0.08})
    for i in range(5):
        trials.append({"ground_truth_label": "Walking", "predicted_label": "Fall", "alert_raised": True, "detection_latency_seconds": 0.10})
    for i in range(2):
        trials.append({"ground_truth_label": "Fall", "predicted_label": "Sitting", "alert_raised": False, "detection_latency_seconds": 0.11})
    for i in range(43):
        trials.append({"ground_truth_label": "Sitting", "predicted_label": "Sitting", "alert_raised": False, "detection_latency_seconds": 0.09})

    metrics = EvaluationEngine.calculate_binary_metrics(trials)

    assert metrics["TP"] == 50
    assert metrics["FP"] == 5
    assert metrics["FN"] == 2
    assert metrics["TN"] == 43
    assert metrics["total_trials"] == 100

    # Accuracy = (50 + 43) / 100 = 93.0%
    assert metrics["accuracy"] == 93.0

    # Precision = 50 / (50 + 5) = 50 / 55 = 90.91%
    assert pytest.approx(metrics["precision"], 0.1) == 90.91

    # Recall = 50 / (50 + 2) = 50 / 52 = 96.15%
    assert pytest.approx(metrics["recall"], 0.1) == 96.15

    # Specificity = 43 / (43 + 5) = 43 / 48 = 89.58%
    assert pytest.approx(metrics["specificity"], 0.1) == 89.58

    # F1 = 2 * (90.909 * 96.154) / (90.909 + 96.154) = 93.46%
    assert pytest.approx(metrics["f1_score"], 0.2) == 93.46


def test_detector_comparison_structure():
    comparison = EvaluationEngine.get_detector_comparison()
    assert len(comparison) == 3
    assert "Baseline" in comparison[0]["Detector Architecture"]
    assert "Temporal" in comparison[1]["Detector Architecture"]
    assert "Random Forest" in comparison[2]["Detector Architecture"]
