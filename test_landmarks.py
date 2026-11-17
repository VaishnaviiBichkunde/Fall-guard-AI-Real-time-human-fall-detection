import cv2

from core.landmark_extractor import LandmarkExtractor
from core.pose_detector import PoseDetector


camera = cv2.VideoCapture(0)
pose_detector = PoseDetector()
landmark_extractor = LandmarkExtractor()

if not camera.isOpened():
    print("ERROR: Could not open the webcam.")
    pose_detector.pose.close()
    exit()

print("Webcam, MediaPipe Pose, and landmark extraction started.")
print("Stand in front of the camera and press 'q' to close.")

try:
    while True:
        success, frame = camera.read()

        if not success:
            print("ERROR: Could not read frame.")
            break

        frame, results = pose_detector.process_frame(frame)
        landmarks = landmark_extractor.extract(results)

        if landmarks:
            print("\033[H\033[J", end="")
            print("Detected landmarks:")
            for name, coordinates in landmarks.items():
                print(
                    f"{name:>14}: "
                    f"x={coordinates['x']:.3f}, "
                    f"y={coordinates['y']:.3f}, "
                    f"z={coordinates['z']:.3f}, "
                    f"visibility={coordinates['visibility']:.3f}"
                )

        cv2.imshow("Landmark Extraction Test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    camera.release()
    pose_detector.pose.close()
    cv2.destroyAllWindows()
    print("Webcam and landmark extraction closed.")
