import cv2
import numpy as np
import threading
import time
import requests
from ultralytics import YOLO

# ---------------- CONFIG ----------------
RTSP_URLS = [
    "rtsp://admin:123456@192.168.0.100:554/ch01.264",
    "rtsp://admin:123456@192.168.0.101:554/ch01.264",
    "rtsp://admin:123456@192.168.0.103:554/ch01.264",
]

PICO_IP = "192.168.0.205"
STOP_DELAY = 2.0

# ---------------- GLOBALS ----------------
frames = [np.zeros((270, 480, 3), dtype=np.uint8) for _ in RTSP_URLS]
detections = [[] for _ in RTSP_URLS]

buzzer_on = False
last_seen = 0
last_api_call = 0

# ---------------- YOLO ----------------
model = YOLO("yolov8n.pt")

# ---------------- CAMERA THREAD ----------------
class CameraThread:
    def __init__(self, url, index):
        self.url = url
        self.index = index
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.running = True

        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        global frames
        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                print(f"Reconnecting Camera {self.index}")
                self.cap.release()
                time.sleep(1)
                self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                continue

            frames[self.index] = cv2.resize(frame, (480, 270))

    def stop(self):
        self.running = False
        self.cap.release()

# ---------------- YOLO THREAD ----------------
def detection_loop():
    global detections, last_seen, buzzer_on, last_api_call

    while True:
        for i, frame in enumerate(frames):

            results = model(frame, verbose=False)[0]

            boxes = []
            detected = False

            for box in results.boxes:
                if int(box.cls[0]) == 0:  # person
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    boxes.append((x1, y1, x2, y2))
                    detected = True

            detections[i] = boxes

            current_time = time.time()

            # -------- DETECTED --------
            if detected:
                last_seen = current_time

                # 🔥 Try ON every 2 sec (handles manual OFF)
                if current_time - last_api_call > 0.5:
                    print("HUMAN DETECTED")

                    try:
                        requests.get(f"http://{PICO_IP}/on", timeout=2)
                        last_api_call = current_time
                        buzzer_on = True  # 🔥 ADD THIS BACK
                    except:
                        print("Pico not reachable")

            # -------- NOT DETECTED --------
            else:
                if (current_time - last_seen > STOP_DELAY):
                    print("NO HUMAN → OFF")

                    try:
                        requests.get(f"http://{PICO_IP}/off", timeout=2)
                        buzzer_on = False
                    except:
                        print("Pico not reachable")

        time.sleep(0.2)  # reduce lag

# ---------------- START ----------------
cams = [CameraThread(url, i) for i, url in enumerate(RTSP_URLS)]

threading.Thread(target=detection_loop, daemon=True).start()

# ---------------- DISPLAY ----------------
while True:
    current_frames = frames.copy()

    for i, frame in enumerate(current_frames):
        # Draw boxes
        for (x1, y1, x2, y2) in detections[i]:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, "Human", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Camera label
        cv2.putText(frame, f"Cam {i+1}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    grid = np.hstack(current_frames)
    grid = cv2.resize(grid, (1200, 400))

    cv2.imshow("YOLO Multi Camera", grid)

    if cv2.waitKey(1) == 27:
        break

# ---------------- CLEANUP ----------------
for cam in cams:
    cam.stop()

cv2.destroyAllWindows()