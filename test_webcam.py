import cv2

# Open the default laptop webcam
camera = cv2.VideoCapture(0)

# Check whether the camera opened successfully
if not camera.isOpened():
    print("ERROR: Could not open the webcam.")
    exit()

print("Webcam started successfully.")
print("Press 'q' to close the webcam.")

while True:
    # Read one frame from the webcam
    success, frame = camera.read()

    # Check whether a frame was captured
    if not success:
        print("ERROR: Could not read frame.")
        break

    # Display the live video
    cv2.imshow("Webcam Test", frame)

    # Press q to exit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Release the webcam
camera.release()

# Close all OpenCV windows
cv2.destroyAllWindows()
print("Webcam closed.")
