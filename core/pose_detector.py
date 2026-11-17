import logging
import threading
import cv2
import mediapipe as mp

logger = logging.getLogger(__name__)


class PoseDetector:
    """
    Real-time MediaPipe pose detector for webcam frames.
    Square padding avoids non-square ROI issues, while video tracking and landmark
    smoothing improve continuity between consecutive frames.
    """

    def __init__(self, min_detection_confidence=0.4, min_tracking_confidence=0.45):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self._lock = threading.Lock()

        self.landmark_spec = self.mp_drawing.DrawingSpec(
            color=(0, 255, 128),  # Vibrant Emerald Green / Cyan for body landmarks
            thickness=3,
            circle_radius=4,
        )
        self.connection_spec = self.mp_drawing.DrawingSpec(
            color=(255, 200, 0),  # Bright Electric Cyan/Yellow for skeleton bones
            thickness=3,
        )

        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process_frame(self, frame):
        if frame is None or frame.size == 0:
            return frame, None

        try:
            h, w = frame.shape[:2]
            # Always ensure the frame sent to MediaPipe is a strict 1:1 square
            if h != w:
                max_dim = max(h, w)
                top = (max_dim - h) // 2
                bottom = max_dim - h - top
                left = (max_dim - w) // 2
                right = max_dim - w - left
                input_frame = cv2.copyMakeBorder(frame, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
            else:
                top, left, max_dim = 0, 0, h
                input_frame = frame

            rgb_frame = cv2.cvtColor(input_frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False

            with self._lock:
                results = self.pose.process(rgb_frame)

            rgb_frame.flags.writeable = True

            if results and results.pose_landmarks:
                # Un-pad normalized landmarks back to original frame dimensions
                for lm in results.pose_landmarks.landmark:
                    lm.x = (lm.x * max_dim - left) / w
                    lm.y = (lm.y * max_dim - top) / h

                self.mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.landmark_spec,
                    connection_drawing_spec=self.connection_spec,
                )

            return frame, results
        except Exception:
            logger.exception("MediaPipe failed to process a webcam frame.")
            return frame, None

    def close(self):
        with self._lock:
            try:
                self.pose.close()
            except Exception:
                pass
