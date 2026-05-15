import cv2
import mediapipe as mp
import time
import requests
import math

# ===================== ESP URLs =====================
BASE_URL = "http://192.168.4.1"
OPEN_GRIPPER_URL = BASE_URL + "/gripper?action=open"
CLOSE_GRIPPER_URL = BASE_URL + "/gripper?action=close"

# ===================== CONNECT CHECK =====================
arm_connected = False
try:
    r = requests.get(BASE_URL, timeout=3)
    arm_connected = r.status_code == 200
except:
    arm_connected = False

print("ARM CONNECTED:", arm_connected)

# ===================== CAMERA =====================
cap = cv2.VideoCapture(0)

# ===================== MEDIAPIPE =====================
mpHands = mp.solutions.hands
hands = mpHands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mpPose = mp.solutions.pose
pose = mpPose.Pose()
mpDraw = mp.solutions.drawing_utils

# ===================== STATE =====================
handOpen = False
gripper_status = None
arm_angle_state = None

last_gripper_time = 0
last_arm_time = 0

GRIPPER_DELAY = 1.0
ARM_DELAY = 3.0

pTime = 0

# ===================== UTILS =====================
def calculate_angle(a, b, c):
    ba = (a[0]-b[0], a[1]-b[1])
    bc = (c[0]-b[0], c[1]-b[1])
    dot = ba[0]*bc[0] + ba[1]*bc[1]
    mag = math.sqrt(ba[0]**2+ba[1]**2)*math.sqrt(bc[0]**2+bc[1]**2)
    return math.degrees(math.acos(dot/mag))

# ===================== MAIN LOOP =====================
while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    hand_results = hands.process(rgb)
    pose_results = pose.process(rgb)

    # ===================== HAND CONTROL =====================
    lmList = []
    if hand_results.multi_hand_landmarks:
        for handLms in hand_results.multi_hand_landmarks:
            for id, lm in enumerate(handLms.landmark):
                lmList.append([id, int(lm.x*w), int(lm.y*h)])
            mpDraw.draw_landmarks(frame, handLms, mpHands.HAND_CONNECTIONS)

    if lmList:
        fingers = []

        # Thumb
        fingers.append(1 if lmList[4][1] > lmList[3][1] else 0)

        # Other fingers
        for tip in [8,12,16,20]:
            fingers.append(1 if lmList[tip][2] < lmList[tip-2][2] else 0)

        totalFingers = fingers.count(1)
        handOpen = totalFingers >= 3

        now = time.time()
        if arm_connected and now - last_gripper_time > GRIPPER_DELAY:
            if handOpen and gripper_status != "open":
                requests.get(OPEN_GRIPPER_URL, timeout=2)
                gripper_status = "open"
                last_gripper_time = now
                print("GRIPPER OPEN")

            elif not handOpen and gripper_status != "close":
                requests.get(CLOSE_GRIPPER_URL, timeout=2)
                gripper_status = "close"
                last_gripper_time = now
                print("GRIPPER CLOSE")

        cv2.putText(frame, f"Fingers: {totalFingers}", (20,80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

    # ===================== POSE CONTROL =====================
    if pose_results.pose_landmarks:
        lm = pose_results.pose_landmarks.landmark

        s = (int(lm[11].x*w), int(lm[11].y*h))
        e = (int(lm[13].x*w), int(lm[13].y*h))
        wri = (int(lm[15].x*w), int(lm[15].y*h))

        angle = calculate_angle(s, e, wri)
        cv2.putText(frame, f"{int(angle)} deg", (e[0]+10, e[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        now = time.time()
        if arm_connected and now - last_arm_time > ARM_DELAY:
            last_arm_time = now

            if angle < 45 and arm_angle_state != 0:
                arm_angle_state = 0
            elif 45 < angle < 60 and arm_angle_state != 15:
                arm_angle_state = 15
            elif 60 < angle < 90 and arm_angle_state != 30:
                arm_angle_state = 30
            elif 90 < angle < 120 and arm_angle_state != 45:
                arm_angle_state = 45
            else:
                arm_angle_state = None

            if arm_angle_state is not None:
                requests.post(f"{BASE_URL}/stepper?num=2&angle={arm_angle_state}", timeout=5)
                requests.post(f"{BASE_URL}/stepper?num=3&angle={arm_angle_state}", timeout=5)
                print("ARM ANGLE:", arm_angle_state)

    # ===================== FPS =====================
    cTime = time.time()
    fps = int(1/(cTime-pTime)) if cTime!=pTime else 0
    pTime = cTime

    cv2.putText(frame, f"FPS: {fps}", (10,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 2)

    cv2.imshow("Hand + Pose Controlled Robot Arm", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
