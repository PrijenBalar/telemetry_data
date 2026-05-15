import cv2
import cv2.aruco as aruco
import numpy as np


# ===================== LOAD CAMERA CALIBRATION =====================
camera_matrix = np.load("cameraMatrix.npy")
dist_coeffs = np.load("distCoeffs.npy")

# ===================== ARUCO SETUP =====================
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_6X6_50)
parameters = aruco.DetectorParameters()
detector = aruco.ArucoDetector(aruco_dict, parameters)

# ===================== CAMERA =====================
cap = cv2.VideoCapture(0)

# ===================== MARKER INFO =====================
MARKER_SIZE_M = 0.053 # marker size in METERS (5 cm)

# 3D object points of marker corners (meters)
obj_points = np.array([
    [-MARKER_SIZE_M/2,  MARKER_SIZE_M/2, 0],
    [ MARKER_SIZE_M/2,  MARKER_SIZE_M/2, 0],
    [ MARKER_SIZE_M/2, -MARKER_SIZE_M/2, 0],
    [-MARKER_SIZE_M/2, -MARKER_SIZE_M/2, 0]
], dtype=np.float32)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    corners, ids, _ = detector.detectMarkers(gray)

    if ids is not None:
        aruco.drawDetectedMarkers(frame, corners, ids)

        for i in range(len(ids)):
            img_points = corners[i][0].astype(np.float32)

            success, rvec, tvec = cv2.solvePnP(
                obj_points,
                img_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )

            if success:
                # ===================== CONVERT TO MILLIMETERS =====================
                x_m, y_m, z_m = tvec.flatten()

                x_mm = x_m * 1000.0
                y_mm = y_m * 1000.0
                z_mm = z_m * 1000.0

                # ===================== DRAW AXIS =====================
                cv2.drawFrameAxes(
                    frame,
                    camera_matrix,
                    dist_coeffs,
                    rvec,
                    tvec,
                    0.03
                )

                # ===================== DISPLAY =====================
                cv2.putText(
                    frame,
                    f"ID:{ids[i][0]}  X:{x_mm:.1f}  Y:{y_mm:.1f}  Z:{z_mm:.1f} mm",
                    (10, 40 + i * 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                # ===================== PRINT (FOR ROBOT USE) =====================
                print(
                    f"Marker {ids[i][0]} -> "
                    f"X:{x_mm:.2f} mm, "
                    f"Y:{y_mm:.2f} mm, "
                    f"Z:{z_mm:.2f} mm"
                )

    cv2.imshow("ArUco solvePnP (mm)", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
