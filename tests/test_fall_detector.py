from core.fall_detector import FallDetector


def test_fall_detector():
    normal_detector = FallDetector()
    assert normal_detector.check_fall(10, 0.01, False) == "Normal Activity"
    assert normal_detector.fall_frame_count == 0

    transient_detector = FallDetector()
    assert transient_detector.check_fall(60, 0.08, True) == "Normal Activity"
    assert transient_detector.fall_frame_count == 1
    assert transient_detector.check_fall(10, 0.01, False) == "Normal Activity"
    assert transient_detector.fall_frame_count == 0

    persistent_detector = FallDetector(required_frames=10)
    for frame_number in range(9):
        assert persistent_detector.check_fall(60, 0.08, True) == "Normal Activity"
        assert persistent_detector.fall_frame_count == frame_number + 1

    assert persistent_detector.check_fall(60, 0.08, True) == "FALL DETECTED"
    assert persistent_detector.fall_frame_count == 10

