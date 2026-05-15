import requests
import time

BASE_URL = "http://192.168.4.1"

for angle in range(0, 91, 10):
    print("Sending angle:", angle)
    requests.post(f"{BASE_URL}/stepper?num=2&angle={angle}", timeout=5)
    requests.post(f"{BASE_URL}/stepper?num=3&angle={angle}", timeout=5)
    time.sleep(2)

for angle in range(90, -1, -10):
    print("Sending angle:", angle)
    requests.post(f"{BASE_URL}/stepper?num=2&angle={angle}", timeout=5)
    requests.post(f"{BASE_URL}/stepper?num=3&angle={angle}", timeout=5)
    time.sleep(2)
