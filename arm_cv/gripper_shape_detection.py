import cv2
import numpy as np
import time


from ArmControl import ArmControl
arm = ArmControl()

gripper_state = "closed"   # "closed" or "open"\
shape_start_time = None

time.sleep(5)
arm.close_gripper()
print("Gripper is closed")


cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    valid_shape_detected = False

    # Flip & crop
    frame = cv2.flip(frame, 1)
    frame = frame[0:800, 0:800]

    # ===== HSV CONVERSION =====
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # ===== WHITE MASK =====
    lower_white = np.array([0, 0, 180])
    upper_white = np.array([179, 50, 255])
    white_mask = cv2.inRange(hsv, lower_white, upper_white)

    # ===== BLACK MASK =====
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([179, 255, 60])
    black_mask = cv2.inRange(hsv, lower_black, upper_black)

    # ===== COMBINE WHITE + BLACK =====
    combined_mask = cv2.bitwise_or(white_mask, black_mask)

    # ===== MORPHOLOGY (REMOVE NOISE) =====
    kernel = np.ones((5, 5), np.uint8)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # ===== EDGES (DEBUG ONLY) =====
    edges = cv2.Canny(combined_mask, 70, 170)

    # ===== FIND CONTOURS =====
    contours, _ = cv2.findContours(
        combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 1000 or area > 9000:
            continue

        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        rect = cv2.minAreaRect(cnt)
        (w, h) = rect[1]
        diameter = max(w, h)

        if w == 0 or h == 0:
            continue

        aspect_ratio = max(w, h) / min(w, h)

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue

        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Draw centroid
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

        circularity = (4 * np.pi * area) / (perimeter * perimeter)
        extent = area / (w * h)

        shape = "Unknown"

        # ===== SHAPE LOGIC =====
        shape = "Unknown"

        if circularity > 0.82 and len(approx) > 6:
            shape = "Circle"
        elif len(approx) == 4 and 0.85 <= aspect_ratio <= 1.15 and extent > 0.75:
            shape = "Square"
        elif len(approx) == 4:
            shape = "Rectangle"

        # ===== 3-SECOND STABLE DETECTION LOGIC =====
        if shape != "Unknown":
            valid_shape_detected = True

            if gripper_state == "closed":
                if shape_start_time is None:
                    shape_start_time = time.time()
                    print(f"👀 {shape} detected → waiting 1.5 seconds...")
                elif time.time() - shape_start_time >= 1.5:
                    print(f"✅ {shape} stable → OPEN gripper")
                    arm.open_gripper()
                    gripper_state = "open"

        #if shape == "Unknown":
        #    continue

        # ===== DRAW ROTATED BOX =====
        box = cv2.boxPoints(rect)
        box = box.astype(int)
        cv2.drawContours(frame, [box], 0, (255, 0, 0), 2)

        cx, cy = int(rect[0][0]), int(rect[0][1])
        cv2.putText(
            frame,
            f"D: {int(diameter)} px",
            (cx - 40, cy + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

        cv2.putText(frame, shape, (cx - 40, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    if not valid_shape_detected:
        shape_start_time = None

        if gripper_state == "open":
            print("❌ Object lost → CLOSE gripper")
            arm.close_gripper()
            gripper_state = "closed"


    # ===== DISPLAY =====
    # cv2.imshow("White Mask", white_mask)
    # cv2.imshow("Black Mask", black_mask)
    # cv2.imshow("Combined Mask", combined_mask)
    # cv2.imshow("Edges (Debug)", edges)
    cv2.imshow("Shape Detection", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break
# ===== CLOSE GRIPPER WHEN OBJECT IS GONE =====




cap.release()
cv2.destroyAllWindows()
