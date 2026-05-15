import cv2
import numpy as np
import glob

# ===================== CHESSBOARD SETTINGS =====================
CHESSBOARD_SIZE = (8, 5)   # inner corners
SQUARE_SIZE = 0.010        # meters (25 mm)

# ===================== PREPARE OBJECT POINTS =====================
objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0],
                       0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
objp *= SQUARE_SIZE

objpoints = []  # 3D points
imgpoints = []  # 2D points

cap = cv2.VideoCapture(1)
count = 0

print("Press 'c' to capture chessboard images")
print("Press 'q' to calibrate and quit")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

    if found:
        cv2.drawChessboardCorners(frame, CHESSBOARD_SIZE, corners, found)

    cv2.imshow("Calibration", frame)
    key = cv2.waitKey(1)

    if key == ord('c') and found:
        objpoints.append(objp)
        corners2 = cv2.cornerSubPix(
            gray, corners, (11,11), (-1,-1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        )
        imgpoints.append(corners2)
        count += 1
        print(f"Captured image {count}")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# ===================== CALIBRATION =====================
ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
    objpoints, imgpoints, gray.shape[::-1], None, None
)

print("Calibration done")
print("Camera Matrix:\n", camera_matrix)
print("Distortion Coeffs:\n", dist_coeffs)

# ===================== SAVE FILES =====================
np.save("cameraMatrix.npy", camera_matrix)
np.save("distCoeffs.npy", dist_coeffs)

print("Saved cameraMatrix.npy and distCoeffs.npy")
