"""
Unit tests for Temporal Fall vs. Sleeping Detection Engine.
"""

import pytest
from core.temporal_fall_detector import TemporalFallDetector


def test_standing_posture_classification():
    detector = TemporalFallDetector()
    features = {
        "body_angle_degrees": 12.0,
        "hip_y": 0.50,
        "body_orientation": "vertical",
        "mean_visibility": 0.95,
        "aspect_ratio": 0.40,
        "left_knee_angle": 175.0,
        "right_knee_angle": 176.0,
    }
    result = detector.update(features)
    assert result["posture"] == "Standing"
    assert result["is_possible_fall"] is False
    assert "NORMAL" in result["status"]


def test_sitting_posture_classification():
    detector = TemporalFallDetector()
    features = {
        "body_angle_degrees": 28.0,
        "hip_y": 0.65,
        "body_orientation": "vertical",
        "mean_visibility": 0.95,
        "aspect_ratio": 0.85,
        "left_knee_angle": 95.0,
        "right_knee_angle": 92.0,
    }
    result = detector.update(features)
    assert result["posture"] == "Sitting"
    assert result["is_possible_fall"] is False
    assert "NORMAL" in result["status"]


def test_bending_posture_classification():
    detector = TemporalFallDetector()
    features = {
        "body_angle_degrees": 45.0,
        "hip_y": 0.55,
        "body_orientation": "vertical",
        "mean_visibility": 0.90,
        "aspect_ratio": 0.70,
        "left_knee_angle": 160.0,
        "right_knee_angle": 165.0,
    }
    result = detector.update(features)
    assert result["posture"] == "Bending"
    assert result["is_possible_fall"] is False
    assert "NORMAL" in result["status"]


def test_lying_resting_without_shock_does_not_trigger_fall():
    """Resting/sleeping horizontally without prior velocity shock must NOT trigger false fall."""
    detector = TemporalFallDetector()
    # Feed frames with gradual transition to horizontal, zero/minimal downward shock
    for _ in range(10):
        features = {
            "body_angle_degrees": 75.0,
            "hip_y": 0.80,
            "body_orientation": "horizontal",
            "mean_visibility": 0.90,
            "aspect_ratio": 1.90,
            "left_knee_angle": 170.0,
            "right_knee_angle": 170.0,
        }
        result = detector.update(features)

    assert result["posture"] == "Intentional Lying Down"
    assert result["is_possible_fall"] is False
    assert "LYING DOWN" in result["status"]
    assert "explanation_evidence" in result


def test_sudden_fall_triggers_possible_fall():
    """Sudden downward velocity drop followed by horizontal angle triggers Possible Fall."""
    detector = TemporalFallDetector(verification_frames=2, high_velocity_threshold=0.03)

    # Frame 1: Upright standing
    f1 = {
        "body_angle_degrees": 10.0,
        "hip_y": 0.40,
        "body_orientation": "vertical",
        "mean_visibility": 0.95,
        "aspect_ratio": 0.40,
        "left_knee_angle": 175.0,
        "right_knee_angle": 175.0,
    }
    detector.update(f1)

    # Frame 2: Rapid downward drop (velocity = 0.85 - 0.40 = 0.45 >> 0.03)
    f2 = {
        "body_angle_degrees": 65.0,
        "hip_y": 0.85,
        "body_orientation": "horizontal",
        "mean_visibility": 0.92,
        "aspect_ratio": 1.85,
        "left_knee_angle": 160.0,
        "right_knee_angle": 160.0,
    }
    detector.update(f2)

    # Frame 3: Sustained horizontal posture
    f3 = {
        "body_angle_degrees": 72.0,
        "hip_y": 0.87,
        "body_orientation": "horizontal",
        "mean_visibility": 0.92,
        "aspect_ratio": 1.90,
        "left_knee_angle": 165.0,
        "right_knee_angle": 165.0,
    }
    result = detector.update(f3)

    assert result["is_possible_fall"] is True
    assert "POSSIBLE FALL" in result["status"]
    assert len(result["explanation_evidence"]) >= 3


def test_low_visibility_returns_uncertain():
    detector = TemporalFallDetector(min_visibility_threshold=0.60)
    features = {
        "body_angle_degrees": 20.0,
        "hip_y": 0.50,
        "mean_visibility": 0.30,  # Below threshold
        "body_orientation": "vertical",
    }
    result = detector.update(features)
    assert "UNCERTAIN" in result["status"]
    assert result["is_possible_fall"] is False
