LANDMARK_INDICES = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


class LandmarkExtractor:
    def extract(self, results):
        if not results or not hasattr(results, "pose_landmarks") or not results.pose_landmarks:
            return None

        landmarks = results.pose_landmarks.landmark
        extracted = {}

        for name, index in LANDMARK_INDICES.items():
            landmark = landmarks[index]
            extracted[name] = {
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z,
                "visibility": landmark.visibility,
            }

        return extracted
