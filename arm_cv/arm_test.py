import time
import requests

BASE_URL = "http://192.168.4.1"

def move_stepper(num, angle):
    url = f"{BASE_URL}/stepper?num={num}&angle={angle}"
    try:
        res = requests.get(url, timeout=10)
        print(res.text, f"stepper {num} angle {angle}")
    except Exception as e:
        print("Error:", e)

# ===================== MAIN LOOP =====================
for i in range(100):

    # Move both steppers to -15
    move_stepper(3, -15)
    move_stepper(2, -15)

    time.sleep(2)

    # Move both steppers back to 0
    move_stepper(3, 0)
    move_stepper(2, 0)

    time.sleep(2)

print("Motion finished")
