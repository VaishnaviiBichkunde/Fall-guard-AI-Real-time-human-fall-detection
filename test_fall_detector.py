from core.fall_detector import FallDetector


detector = FallDetector(required_frames=3)

print("Testing normal activity...")
for _ in range(5):
    status = detector.check_fall(
        body_angle=10,
        hip_movement=0.005,
        horizontal=False,
    )
    print(status)

print("\nTesting possible fall...")
for frame in range(1, 6):
    status = detector.check_fall(
        body_angle=60,
        hip_movement=0.08,
        horizontal=True,
    )
    print(f"Frame {frame}: {status}")
