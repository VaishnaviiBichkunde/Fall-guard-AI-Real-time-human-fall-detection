import time
import cv2

from core.fall_detector import FallDetector
from core.feature_calculator import FeatureCalculator
from core.landmark_extractor import LandmarkExtractor
from core.pose_detector import PoseDetector


def main():
    # Initialize webcam (0 is default built-in camera)
    camera = cv2.VideoCapture(0)
    pose_detector = PoseDetector()
    landmark_extractor = LandmarkExtractor()
    feature_calculator = FeatureCalculator()
    fall_detector = FallDetector(required_frames=3)

    if not camera.isOpened():
        print("ERROR: Could not open the webcam. Please verify webcam access and index.")
        pose_detector.pose.close()
        return

    print("==================================================")
    print(" REAL-TIME HUMAN FALL DETECTION & MONITORING MODULE")
    print("==================================================")
    print("Webcam, MediaPipe Pose, and Fall Detector initialized.")
    print("Press 'q' or 'Q' in the webcam window to exit.")
    print("==================================================")

    prev_time = time.time()
    prev_hip_y = None

    try:
        while True:
            success, frame = camera.read()

            if not success or frame is None:
                print("ERROR: Could not read frame from webcam.")
                break

            # Process frame for human pose detection
            frame, results = pose_detector.process_frame(frame)
            landmarks = landmark_extractor.extract(results)
            features = feature_calculator.calculate(landmarks)

            # Calculate FPS
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
            prev_time = curr_time

            person_detected = landmarks is not None
            current_status = "Normal Activity"
            body_angle = 0.0

            if person_detected and features:
                body_angle = features["body_angle_degrees"]
                hip_y = features["hip_y"]

                hip_movement = (hip_y - prev_hip_y) if prev_hip_y is not None else 0.0
                prev_hip_y = hip_y

                horizontal = features["body_orientation"] == "horizontal"
                current_status = fall_detector.check_fall(
                    body_angle=body_angle,
                    hip_movement=hip_movement,
                    horizontal=horizontal,
                )
            else:
                prev_hip_y = None
                fall_detector.fall_frame_count = 0
                current_status = "No Person"

            # Render Overlay Information on the Frame
            # 1. System Status & Activity Banner
            if current_status == "FALL DETECTED":
                status_text = "ALERT: FALL DETECTED!"
                status_color = (0, 0, 255)  # Bright Red
            elif person_detected:
                status_text = "PERSON DETECTED (NORMAL)"
                status_color = (0, 255, 0)  # Green
            else:
                status_text = "NO PERSON DETECTED"
                status_color = (128, 128, 128)  # Gray

            cv2.putText(
                frame,
                status_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                status_color,
                2,
                cv2.LINE_AA,
            )

            # 2. Body Angle & Orientation
            cv2.putText(
                frame,
                f"Angle: {body_angle:.1f} deg",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),  # Cyan
                2,
                cv2.LINE_AA,
            )

            # 3. Real-Time FPS Value
            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),  # White
                2,
                cv2.LINE_AA,
            )

            # Display the live frame
            cv2.imshow("Real-Time Human Fall Detection", frame)

            # Exit if 'q' or 'Q' key is pressed
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                print("User exited webcam view.")
                break

    finally:
        # Clean up camera and OpenCV windows
        camera.release()
        pose_detector.pose.close()
        cv2.destroyAllWindows()
        print("Webcam and MediaPipe Pose resources released successfully.")


if __name__ == "__main__":
    main()


