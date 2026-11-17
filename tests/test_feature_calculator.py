import math
from core.feature_calculator import FeatureCalculator


def test_feature_calculator():
    landmarks = {
        "left_shoulder": {"x": 0.45, "y": 0.30},
        "right_shoulder": {"x": 0.55, "y": 0.30},
        "left_hip": {"x": 0.45, "y": 0.60},
        "right_hip": {"x": 0.55, "y": 0.60},
        "left_knee": {"x": 0.45, "y": 0.80},
        "right_knee": {"x": 0.55, "y": 0.80},
        "left_ankle": {"x": 0.45, "y": 0.95},
        "right_ankle": {"x": 0.55, "y": 0.95},
    }

    features = FeatureCalculator().calculate(landmarks)

    assert features["shoulder_center"] == {"x": 0.5, "y": 0.3}
    assert features["hip_center"] == {"x": 0.5, "y": 0.6}
    assert math.isclose(features["body_angle_degrees"], 0.0)
    assert math.isclose(features["hip_y"], 0.6)
    assert features["body_orientation"] == "vertical"

