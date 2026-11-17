"""
Trains a Random Forest activity classification model for Fall Guard AI.
Saves model and metadata using Joblib.
"""

import os
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "random_forest_activity.joblib")

CLASSES = [
    "Standing",
    "Sitting",
    "Bending",
    "Lying Down / Resting",
    "Possible Fall",
]


def generate_synthetic_dataset(samples_per_class: int = 250, random_state: int = 42):
    """
    Generates realistic biomechanical movement feature samples based on
    human anatomical geometry and physical velocity constraints.
    """
    np.random.seed(random_state)
    X = []
    y = []

    # Class 0: Standing (low angle, vertical orientation, high hip, zero velocity)
    for _ in range(samples_per_class):
        angle = np.random.normal(10.0, 5.0)
        ratio = np.random.normal(0.35, 0.1)
        hip_y = np.random.normal(0.45, 0.05)
        torso_len = np.random.normal(0.35, 0.03)
        shoulder_w = np.random.normal(0.18, 0.02)
        knee_angle = np.random.normal(175.0, 5.0)
        dx = abs(np.random.normal(0.04, 0.02))
        dy = abs(np.random.normal(0.35, 0.03))
        vis = np.random.uniform(0.85, 1.0)
        aspect = shoulder_w / (torso_len + 1e-5)
        vel = np.random.normal(0.002, 0.002)
        acc = np.random.normal(0.001, 0.001)
        X.append([angle, ratio, hip_y, torso_len, shoulder_w, knee_angle, dx, dy, vis, aspect, vel, acc])
        y.append(0)

    # Class 1: Sitting (low angle, upright torso, lowered hip, bent knees)
    for _ in range(samples_per_class):
        angle = np.random.normal(18.0, 6.0)
        ratio = np.random.normal(0.45, 0.1)
        hip_y = np.random.normal(0.68, 0.04)
        torso_len = np.random.normal(0.32, 0.03)
        shoulder_w = np.random.normal(0.18, 0.02)
        knee_angle = np.random.normal(95.0, 15.0)
        dx = abs(np.random.normal(0.06, 0.03))
        dy = abs(np.random.normal(0.30, 0.03))
        vis = np.random.uniform(0.80, 0.98)
        aspect = shoulder_w / (torso_len + 1e-5)
        vel = np.random.normal(0.005, 0.004)
        acc = np.random.normal(0.002, 0.002)
        X.append([angle, ratio, hip_y, torso_len, shoulder_w, knee_angle, dx, dy, vis, aspect, vel, acc])
        y.append(1)

    # Class 2: Bending (moderate angle, feet grounded, low downward velocity)
    for _ in range(samples_per_class):
        angle = np.random.normal(42.0, 8.0)
        ratio = np.random.normal(0.70, 0.15)
        hip_y = np.random.normal(0.55, 0.05)
        torso_len = np.random.normal(0.30, 0.03)
        shoulder_w = np.random.normal(0.20, 0.02)
        knee_angle = np.random.normal(155.0, 15.0)
        dx = abs(np.random.normal(0.18, 0.04))
        dy = abs(np.random.normal(0.22, 0.04))
        vis = np.random.uniform(0.80, 0.95)
        aspect = shoulder_w / (torso_len + 1e-5)
        vel = np.random.normal(0.012, 0.006)
        acc = np.random.normal(0.005, 0.003)
        X.append([angle, ratio, hip_y, torso_len, shoulder_w, knee_angle, dx, dy, vis, aspect, vel, acc])
        y.append(2)

    # Class 3: Lying Down / Resting (high angle, horizontal ratio, zero velocity)
    for _ in range(samples_per_class):
        angle = np.random.normal(78.0, 8.0)
        ratio = np.random.normal(1.8, 0.4)
        hip_y = np.random.normal(0.82, 0.05)
        torso_len = np.random.normal(0.32, 0.03)
        shoulder_w = np.random.normal(0.22, 0.03)
        knee_angle = np.random.normal(160.0, 20.0)
        dx = abs(np.random.normal(0.30, 0.05))
        dy = abs(np.random.normal(0.08, 0.03))
        vis = np.random.uniform(0.70, 0.95)
        aspect = shoulder_w / (torso_len + 1e-5)
        vel = np.random.normal(0.001, 0.001)  # Zero/negligible downward velocity
        acc = np.random.normal(0.0005, 0.0005)
        X.append([angle, ratio, hip_y, torso_len, shoulder_w, knee_angle, dx, dy, vis, aspect, vel, acc])
        y.append(3)

    # Class 4: Possible Fall (high angle, high downward velocity shock)
    for _ in range(samples_per_class):
        angle = np.random.normal(75.0, 9.0)
        ratio = np.random.normal(1.7, 0.4)
        hip_y = np.random.normal(0.84, 0.05)
        torso_len = np.random.normal(0.31, 0.03)
        shoulder_w = np.random.normal(0.22, 0.03)
        knee_angle = np.random.normal(140.0, 30.0)
        dx = abs(np.random.normal(0.29, 0.05))
        dy = abs(np.random.normal(0.09, 0.03))
        vis = np.random.uniform(0.70, 0.95)
        aspect = shoulder_w / (torso_len + 1e-5)
        vel = np.random.normal(0.055, 0.015)  # High vertical drop velocity
        acc = np.random.normal(0.035, 0.010)  # High kinetic impact
        X.append([angle, ratio, hip_y, torso_len, shoulder_w, knee_angle, dx, dy, vis, aspect, vel, acc])
        y.append(4)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def train_and_save_model():
    print("Generating feature dataset...")
    X, y = generate_synthetic_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=4,
        random_state=42,
        class_weight="balanced",
    )

    clf.fit(X_train, y_train)

    train_score = clf.score(X_train, y_train)
    test_score = clf.score(X_test, y_test)
    cv_scores = cross_val_score(clf, X, y, cv=5)

    print(f"Training Accuracy: {train_score * 100:.2f}%")
    print(f"Test Accuracy: {test_score * 100:.2f}%")
    print(f"5-Fold CV Mean: {cv_scores.mean() * 100:.2f}% (+/- {cv_scores.std() * 100:.2f}%)")

    y_pred = clf.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=CLASSES))

    model_data = {
        "model": clf,
        "classes": CLASSES,
        "train_accuracy": float(train_score),
        "test_accuracy": float(test_score),
        "cv_mean": float(cv_scores.mean()),
    }

    joblib.dump(model_data, MODEL_PATH)
    print(f"\nModel successfully saved to: {MODEL_PATH}")
    return model_data


if __name__ == "__main__":
    train_and_save_model()
