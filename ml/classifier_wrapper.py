"""
Runtime ML Classifier Wrapper for Fall Guard AI.
Loads trained Random Forest model and predicts activity class probabilities.
"""

import os
import logging
from typing import Any, Dict, Optional, Tuple
import joblib
import numpy as np

from ml.feature_pipeline import FeaturePipeline

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "models",
    "random_forest_activity.joblib",
)


class ActivityClassifierWrapper:
    """Wrapper for inference with the trained Random Forest model."""

    def __init__(self):
        self.pipeline = FeaturePipeline()
        self.model = None
        self.classes = [
            "Standing",
            "Sitting",
            "Bending",
            "Lying Down / Resting",
            "Possible Fall",
        ]
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                data = joblib.load(MODEL_PATH)
                self.model = data.get("model")
                self.classes = data.get("classes", self.classes)
                self.is_loaded = True
                logger.info("Random Forest activity model loaded successfully.")
            except Exception as err:
                logger.warning("Could not load Random Forest model: %s", err)
                self.is_loaded = False
        else:
            self.is_loaded = False

    def predict(
        self,
        features: Optional[Dict[str, Any]],
        velocity: float = 0.0,
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Predicts activity class from features vector.
        Returns (predicted_class, confidence, probabilities_dict).
        """
        if features is None:
            return "Unknown", 0.0, {}

        # If model is not loaded yet, attempt reload
        if not self.is_loaded:
            self._load_model()

        vector = self.pipeline.extract_vector(features, velocity=velocity)
        if vector is None:
            return "Unknown", 0.0, {}

        if self.is_loaded and self.model is not None:
            try:
                probs = self.model.predict_proba([vector])[0]
                pred_idx = int(np.argmax(probs))
                pred_class = self.classes[pred_idx]
                confidence = float(probs[pred_idx])
                prob_dict = {cls_name: float(p) for cls_name, p in zip(self.classes, probs)}
                return pred_class, confidence, prob_dict
            except Exception as err:
                logger.warning("Model inference error: %s", err)

        # Heuristic fallback if model not loaded
        angle = features.get("body_angle_degrees", 0.0)
        if angle > 50.0 and velocity > 0.03:
            return "Possible Fall", 0.85, {"Possible Fall": 0.85}
        elif angle > 50.0:
            return "Lying Down / Resting", 0.90, {"Lying Down / Resting": 0.90}
        elif angle > 28.0:
            return "Bending", 0.75, {"Bending": 0.75}
        else:
            return "Standing", 0.95, {"Standing": 0.95}
