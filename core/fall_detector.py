class FallDetector:
    def __init__(self, required_frames=10):
        # Number of consecutive frames required before confirming a fall
        self.required_frames = required_frames

        # Counter for consecutive possible-fall frames
        self.fall_frame_count = 0

        # Current detection status
        self.status = "Normal Activity"

    def check_fall(self, body_angle, hip_movement, horizontal):
        # 1. Torso tilt angle is large (over 38 degrees from vertical)
        angle_condition = abs(body_angle) > 38.0

        # 2. Body orientation is horizontal (lying down)
        horizontal_condition = horizontal

        # 3. Dynamic rapid drop OR static fallen/lying posture
        # A fall condition is met if the body is tilted/horizontal OR rapid downward movement occurs
        possible_fall = angle_condition or horizontal_condition or (hip_movement > 0.02)

        if possible_fall:
            self.fall_frame_count += 1
        else:
            self.fall_frame_count = max(0, self.fall_frame_count - 1)

        if self.fall_frame_count >= self.required_frames:
            self.status = "FALL DETECTED"
        else:
            self.status = "Normal Activity"

        return self.status
