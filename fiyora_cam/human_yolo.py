import cv2
import numpy as np
import threading
import time
import requests
import os
import math
from ultralytics import YOLO


RTSP_URLS = [
    "rtsp://192.168.144.108:554/stream=2",              # Cam 1
    "rtsp://admin:123456@192.168.144.100:554/ch01.264", # Cam 2
    "rtsp://admin:123456@192.168.144.101:554/ch01.264", # Cam 3
    "rtsp://admin:123456@192.168.144.103:554/ch01.264", # Cam 4
]

PICO_IP = "192.168.144.205"
STOP_DELAY = 2.0

# ---------------- GLOBALS ----------------
cam_data = [{"frame": None, "detections": []} for _ in RTSP_URLS]
last_seen = 0
last_api_call = 0

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
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.cap.release()
                time.sleep(1)
                self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                continue

            cam_data[self.index]["frame"] = cv2.resize(frame, (480, 270))

    def stop(self):
        self.running = False
        self.cap.release()

# ---------------- DETECTION LOOP ----------------
def detection_loop():
    global last_seen, last_api_call

    while True:
        any_human_found = False

        for i in range(len(RTSP_URLS)):
            if i == 0:
                cam_data[i]["detections"] = []
                continue

            data = cam_data[i]
            if data["frame"] is not None:
                # Detect only humans (class 0)
                results = model.predict(data["frame"], conf=0.4, classes=[0], verbose=False)[0]

                boxes = []
                for box in results.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    boxes.append((x1, y1, x2, y2))
                    any_human_found = True

                cam_data[i]["detections"] = boxes

        # Pico Control Logic
        current_time = time.time()
        if any_human_found:
            last_seen = current_time
            if current_time - last_api_call > 0.8:
                try:
                    requests.get(f"http://{PICO_IP}/on", timeout=0.3)
                    last_api_call = current_time
                except:
                    pass
        else:
            if (current_time - last_seen > STOP_DELAY):
                try:
                    requests.get(f"http://{PICO_IP}/off", timeout=0.3)
                except:
                    pass

        time.sleep(0.01)

# ---------------- START ----------------
cams = [CameraThread(url, i) for i, url in enumerate(RTSP_URLS)]
threading.Thread(target=detection_loop, daemon=True).start()

# ---------------- DISPLAY ----------------
while True:
    display_frames = []

    for i in range(len(RTSP_URLS)):
        data = cam_data[i]
        # Copy the frame for display or use black if not loaded
        f = data["frame"].copy() if data["frame"] is not None else np.zeros((270, 480, 3), dtype=np.uint8)

        # Draw boxes (will be empty for Cam 1)
        for (x1, y1, x2, y2) in data["detections"]:
            cv2.rectangle(f, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(f, "Human", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Labels
        label = f"Cam {i + 1}"
        if i == 0: label += " (Live Only)"
        cv2.putText(f, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        display_frames.append(f)

    # Grid Assembly
    n = len(display_frames)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    while len(display_frames) < rows * cols:
        display_frames.append(np.zeros((270, 480, 3), dtype=np.uint8))

    grid_rows = []
    for i in range(rows):
        row = np.hstack(display_frames[i * cols:(i + 1) * cols])
        grid_rows.append(row)

    cv2.imshow("Multi-Cam Human Watch", np.vstack(grid_rows))
    if cv2.waitKey(1) == 27: break

for cam in cams: cam.stop()
cv2.destroyAllWindows()