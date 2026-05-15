import cv2
import mediapipe as mp
import time

cap = cv2.VideoCapture(0)

mpPose = mp.solutions.pose
pose = mpPose.Pose()
mpDraw = mp.solutions.drawing_utils

pTime = 0

while True:
    success, img = cap.read()
    img = cv2.flip(img, 1)

    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = pose.process(imgRGB)

    h, w, c = img.shape

    if results.pose_landmarks:
        lmList = []

        for id, lm in enumerate(results.pose_landmarks.landmark):
            cx, cy = int(lm.x * w), int(lm.y * h)
            lmList.append([id, cx, cy])

            # draw joints
            cv2.circle(img, (cx, cy), 5, (255, 0, 0), cv2.FILLED)

        # Right arm landmarks
        r_shoulder = lmList[12][1], lmList[12][2]
        r_elbow    = lmList[14][1], lmList[14][2]
        r_wrist    = lmList[16][1], lmList[16][2]

        # Draw arm lines
        cv2.line(img, r_shoulder, r_elbow, (0,255,0), 3)
        cv2.line(img, r_elbow, r_wrist, (0,255,0), 3)

        # Show points
        cv2.circle(img, r_shoulder, 10, (0,0,255), cv2.FILLED)
        cv2.circle(img, r_elbow, 10, (0,0,255), cv2.FILLED)
        cv2.circle(img, r_wrist, 10, (0,0,255), cv2.FILLED)

    # FPS
    cTime = time.time()
    fps = 1/(cTime-pTime)
    pTime = cTime

    cv2.putText(img, f"FPS:{int(fps)}", (10,30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

    cv2.imshow("Arm Tracking", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
