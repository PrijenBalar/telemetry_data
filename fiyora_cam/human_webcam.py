import cv2
import time
from ultralytics import YOLO

# ---------------- CONFIG ----------------
model = YOLO("yolo26n.pt")
# model.to("cuda")  # use GPU (Jetson / laptop GPU)

cap = cv2.VideoCapture(0)

prev_time = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.resize(frame, (640, 480))

    # ---------------- LATENCY START ----------------
    start_time = time.time()

    results = model(frame, conf=0.4, classes=[0], verbose=False)[0]

    # ---------------- LATENCY END ----------------
    end_time = time.time()
    latency_ms = (end_time - start_time) * 1000

    # Draw detections
    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
        cv2.putText(frame, "Human", (x1, y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    # ---------------- FPS ----------------
    curr_time = time.time()
    fps = 1 / (curr_time - prev_time)
    prev_time = curr_time

    # ---------------- DISPLAY ----------------
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

    cv2.putText(frame, f"Latency: {latency_ms:.1f} ms", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

    cv2.imshow("Laptop Camera Detection", frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()