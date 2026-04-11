import cv2
import numpy as np
import threading
import time
import math
import requests

RTSP_URLS = [
    "rtsp://admin:123456@192.168.0.100:554/ch01.264",
    "rtsp://admin:123456@192.168.0.101:554/ch01.264",
    "rtsp://admin:123456@192.168.0.102:554/ch01.264",
    "rtsp://admin:123456@192.168.0.103:554/ch01.264",
]
PICO_IP = "192.168.0.205"

triggered = False
last_seen = 0
trigger_time = 0
buzzer_on = False

STOP_DELAY = 5.0
BUZZER_DELAY = 5.0

# Shared frames
frames = [np.zeros((270, 480, 3), dtype=np.uint8) for _ in RTSP_URLS]


def human_detection(frame):
    global last_seen, buzzer_on, trigger_time, triggered

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower_green = np.array([50, 120, 120])
    upper_green = np.array([80, 255, 255])

    mask = cv2.inRange(hsv, lower_green, upper_green)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected = False

    for cnt in contours:
        area = cv2.contourArea(cnt)

        # 1. Ignore very small areas (noise)
        if area < 2000:
            continue

        # 2. Check Solidity (Area / Convex Hull Area)
        # A solid object (like a box) has high solidity, unlike jagged grass patches.
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)

        # Avoid division by zero
        if hull_area == 0:
            continue

        solidity = float(area) / hull_area

        # Require the shape to be at least 80% solid
        if solidity < 0.8:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / float(h)

        # 3. Check Extent (Area / Bounding Box Area)
        extent = float(area) / (w * h)

        # 4. Apply combined aspect ratio and extent filters
        if 0.3 < aspect_ratio < 3.0 and extent > 0.5:

            # 5. Polygon Approximation
            # Simplify the geometry to count corners. A box should have ~4-6 corners depending on perspective.
            epsilon = 0.04 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)

            if 4 <= len(approx) <= 6:
                detected = True
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # ---- TRIGGER ----
    current_time = time.time()

    if detected:
        last_seen = current_time

        if not triggered:
            print("TRIGGER - HUMAN DETECTED")
            triggered = True

        if not buzzer_on:
            try:
                requests.get(f"http://{PICO_IP}/on", timeout=5)
                buzzer_on = True
            except:
                print("Pico not reachable")

    else:
        if triggered and (current_time - last_seen > STOP_DELAY):
            print("STOP")
            triggered = False

            if buzzer_on:
                try:
                    requests.get(f"http://{PICO_IP}/off", timeout=2)
                    buzzer_on = False
                except:
                    print("Pico not reachable")


class CameraThread:
    def __init__(self, url, index):
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.index = index
        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        global frames
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                frames[self.index] = cv2.resize(frame, (480, 270))
            else:
                frames[self.index] = np.zeros((270, 480, 3), dtype=np.uint8)

    def stop(self):
        self.running = False
        self.cap.release()


# Start all camera threads
cams = [CameraThread(url, i) for i, url in enumerate(RTSP_URLS)]

while True:
    current_frames = frames.copy()
    n = len(current_frames)

    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    # Fill empty
    while len(current_frames) < rows * cols:
        current_frames.append(np.zeros((270, 480, 3), dtype=np.uint8))
        # current_frames.append(np.zeros((540, 720, 3), dtype=np.uint8))


    # Build grid
    grid_rows = []
    for i in range(rows):
        row = np.hstack(current_frames[i * cols:(i + 1) * cols])
        grid_rows.append(row)

    grid = np.vstack(grid_rows)

    # Optional: force rendering size
    grid = cv2.resize(grid, (1200, 700))

    # Run the detection on the grid
    human_detection(grid)

    cv2.imshow("Multi-thread Grid", grid)

    if cv2.waitKey(1) == 27:  # Press ESC to exit
        break

# Stop threads
for cam in cams:
    cam.stop()

cv2.destroyAllWindows()
