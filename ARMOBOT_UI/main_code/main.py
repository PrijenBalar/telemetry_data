import network
import socket
import time
from machine import Pin
import machine
import utime
import json
import gc

delay = 300
# Import DNS Server for captive portal
try:
    from microDNSSrv import MicroDNSSrv

    DNS_AVAILABLE = True
except:
    DNS_AVAILABLE = False
    print("⚠️ DNS server not available")

# Access Point credentials
AP_SSID = 'RoboticArm_AP'
AP_PASSWORD = '12345678'


class Gripper:
    def __init__(self):
        # --- Servo Configuration ---
        SERVO_PIN = 21
        self.servo = machine.PWM(machine.Pin(SERVO_PIN))
        self.servo.freq(50)

        self.MIN_DUTY = 1638
        self.MAX_DUTY = 8192

    def set_angle(self, angle):
        duty = int((angle / 180) * (self.MAX_DUTY - self.MIN_DUTY) + self.MIN_DUTY)
        self.servo.duty_u16(duty)

    def open(self):
        self.set_angle(0)
        utime.sleep_ms(500)

    def close(self):
        self.set_angle(85)
        utime.sleep_ms(500)


class Joint:
    def __init__(self,limit_pin, dir, pulse, maxDegree, minDegree, maxPulse, degreeToPulseRatio , delay=delay):
        self.limit_pin = Pin(limit_pin, Pin.IN, Pin.PULL_UP)
        self.dirPin = Pin(dir, Pin.OUT)
        self.pulsePin = Pin(pulse, Pin.OUT)
        self.maxDegree = maxDegree
        self.minDegree = minDegree
        self.degreeToPulseRatio = degreeToPulseRatio
        self.maxPulse = maxPulse
        self.currentDegree = 0
        self.currentStep = 0

        # 🔹 Non-blocking state
        self.steps_remaining = 0
        self.direction = 1
        self.last_step_time = time.ticks_us()
        self.delay = delay

    def jointDir(self, value):
        self.dirPin.value(value)

    def jointPul(self, value):
        self.pulsePin.value(value)


# Stepper parameters
maxDegree1 = 175.0
minDegree1 = -175.0
maxPulse1 = 3875

minDegree2 = -30.0
maxDegree2 = 110.0
degreeToPulseRatio2 = 2625.0 / 90.0

pulsesPerDegree3 = 2500.0 / 90.0
minDegree3 = -90.0
maxDegree3 = 80.0

saved_movement_1 = []
saved_movement_2 = []

min_s2 = -20
max_s2 = 70
min_s3 = -90
max_s3 = 90
current_position_json = b'{"joint1":0,"joint2":0,"joint3":0}'


import math
from math import cos, sin, atan2, acos

l1 = 18
l2 = 21
l3 = 35


def solve_d3(d2):
    global max_s3, min_s3
    d2_rad = math.radians(d2)
    value = (l1 + l2 * math.cos(d2_rad)) / l3

    if value > 1 or value < -1:
        return None

    asin_val = math.degrees(math.asin(value))
    d3_1 = d2 - asin_val
    d3_2 = d2 - (180 - asin_val)

    max_s3 = int(-d3_2)
    min_s3 = int(d3_1)
    print(f"Updated Stepper 3 range: min={min_s3}, max={max_s3}")
    return -d3_1, -d3_2


def solve_d2(d3_degrees):
    global max_s2, min_s2
    d3 = math.radians(d3_degrees)

    a = l2 + l3 * math.sin(d3)
    b = l3 * math.cos(d3)
    c = -l1

    R = math.sqrt(a * a + b * b)

    if abs(c) > R:
        return None

    phi = math.atan2(b, a)
    psi = math.acos(c / R)

    d2_1 = math.degrees(phi + psi)
    d2_2 = math.degrees(phi - psi)

    if -int(d2_2) > 70:
        max_s2 = 70
    else:
        max_s2 = -int(d2_2) - 5

    if -int(d2_1) < -20:
        min_s2 = -20
    else:
        min_s2 = -int(d2_1)

    print(f"Updated Stepper 2 range: min={min_s2}, max={max_s2}")
    return d2_1, d2_2


def create_access_point():
    """Create WiFi Access Point with DNS"""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    ap_ip = '192.168.4.1'
    ap.ifconfig((ap_ip, '255.255.255.0', ap_ip, ap_ip))
    ap.config(essid=AP_SSID, password=AP_PASSWORD)

    while not ap.active():
        time.sleep(0.1)

    print("✅ Access Point Active!")
    print(f"SSID: {AP_SSID}")
    print(f"Password: {AP_PASSWORD}")
    print(f"IP Address: {ap.ifconfig()[0]}")

    if DNS_AVAILABLE:
        dns_domains = {"*": ap_ip}
        if MicroDNSSrv.Create(dns_domains):
            print("✅ DNS Server started")
        else:
            print("⚠️ DNS Server failed")

    return ap




def stepper_update(joint: Joint):
    
    joint.currentDegree = (joint.currentStep/joint.degreeToPulseRatio)
    update_position_cache()
    if joint.steps_remaining <= 0:
        return

    if joint.limit_pin.value() != 1:
        now = time.ticks_us()

        if time.ticks_diff(now, joint.last_step_time) >= joint.delay:
            joint.dirPin.value(joint.direction)
            joint.pulsePin.value(1)
            time.sleep_us(1)          # tiny pulse width
            joint.pulsePin.value(0)

            joint.steps_remaining -= 1
            joint.last_step_time = now
            
            if joint.direction:
                joint.currentStep += 1
            else:
                joint.currentStep -= 1


def move_stepper(target_degree, joint: Joint):
    target_degree = max(min(target_degree, joint.maxDegree), joint.minDegree)
    degree_delta = target_degree - joint.currentDegree
    pulse_delta = int(abs(degree_delta) * joint.degreeToPulseRatio)

    if pulse_delta == 0:
        return

    joint.direction = 1 if degree_delta > 0 else 0
    joint.steps_remaining = pulse_delta

    print(f"Stepper scheduled → {joint.currentDegree}° ({pulse_delta} steps)")



def calibrate_steppers(joint1: Joint, joint2: Joint, joint3: Joint):
    limit_switch_1 = joint1.limit_pin
    limit_switch_2 = joint2.limit_pin
    limit_switch_3 = joint3.limit_pin

    joint1.jointDir(1)
    joint2.jointDir(0)
    joint3.jointDir(1)

    phase1 = "forward"
    phase2 = "backward"
    phase3 = "backward"

    target_steps_1_back = int(153 / (joint1.maxDegree / joint1.maxPulse))
    target_steps_2_forward = int(31 * joint2.degreeToPulseRatio)
    target_steps_3_forward = int(85 * joint3.degreeToPulseRatio)

    steps_1_back_done = steps_2_forward_done = steps_3_forward_done = 0
    done1 = done2 = done3 = False

    last_step_time_1 = last_step_time_2 = last_step_time_3 = time.ticks_us()
    pulse_delay_1 = pulse_delay_2 = pulse_delay_3 = 600

    print("Calibrating steppers...")
    while not (done1 and done2 and done3):
        now = time.ticks_us()

        if not done1:
            if phase1 == "forward":
                if limit_switch_1.value() == 1:
                    joint1.jointDir(0)
                    phase1 = "backward"
                    steps_1_back_done = 0
                elif time.ticks_diff(now, last_step_time_1) >= pulse_delay_1:
                    joint1.jointPul(1)
                    time.sleep_us(delay)
                    joint1.jointPul(0)
                    last_step_time_1 = now

            elif phase1 == "backward" and steps_1_back_done < target_steps_1_back:
                if time.ticks_diff(now, last_step_time_1) >= pulse_delay_1:
                    joint1.jointPul(1)
                    time.sleep_us(delay)
                    joint1.jointPul(0)
                    steps_1_back_done += 1
                    last_step_time_1 = now
            else:
                done1 = True

        if not done2:
            if phase2 == "backward":
                if limit_switch_2.value() == 1:
                    print("trigger limit 2")
                    joint2.jointDir(1)
                    phase2 = "forward"
                    steps_2_forward_done = 0
                elif time.ticks_diff(now, last_step_time_2) >= pulse_delay_2:
                    joint2.jointPul(1)
                    time.sleep_us(delay)
                    joint2.jointPul(0)
                    last_step_time_2 = now
            elif phase2 == "forward" and steps_2_forward_done < target_steps_2_forward:
                if time.ticks_diff(now, last_step_time_2) >= 400:
                    joint2.jointPul(1)
                    time.sleep_us(delay)
                    joint2.jointPul(0)
                    steps_2_forward_done += 1
                    last_step_time_2 = now
            else:
                done2 = True

        if not done3:
            if phase3 == "backward":
                if limit_switch_3.value() == 1:
                    joint3.jointDir(0)
                    phase3 = "forward"
                    steps_3_forward_done = 0
                elif time.ticks_diff(now, last_step_time_3) >= pulse_delay_3:
                    joint3.jointPul(1)
                    time.sleep_us(delay)
                    joint3.jointPul(0)
                    last_step_time_3 = now
            elif phase3 == "forward" and steps_3_forward_done < target_steps_3_forward:
                if time.ticks_diff(now, last_step_time_3) >= 400:
                    joint3.jointPul(1)
                    time.sleep_us(delay)
                    joint3.jointPul(0)
                    steps_3_forward_done += 1
                    last_step_time_3 = now
            else:
                done3 = True

    joint1.currentDegree = 0
    joint2.currentDegree = 0
    joint3.currentDegree = 0

    print("✅ Calibration complete!")


def send_response(cl, response):
    """Send response in chunks to avoid EIO error"""
    try:
        cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')

        chunk_size = 512
        response_bytes = response.encode('utf-8')

        for i in range(0, len(response_bytes), chunk_size):
            chunk = response_bytes[i:i + chunk_size]
            cl.send(chunk)
            time.sleep_ms(10)
    except Exception as e:
        print(f"Send error: {e}")


def update_position_cache():
    global current_position_json
    current_position_json = (
        b'{"joint1":%d,"joint2":%d,"joint3":%d}' %
        (joint1.currentDegree, joint2.currentDegree, joint3.currentDegree)
    )



def web_page():
    s1 = int(joint1.currentDegree)
    s2 = int(joint2.currentDegree)
    s3 = int(joint3.currentDegree)

    # Updated HTML - removed "stepper" word and reordered sections
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Robotic Arm Control</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);color:#fff;min-height:100vh}}
.banner{{width:100%;background:#000;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.5);position:relative;margin-bottom:0}}
.banner img{{width:100%;height:auto;max-height:250px;object-fit:cover;display:block}}
.banner-text{{background:linear-gradient(to bottom,rgba(15,32,39,0.95),rgba(15,32,39,1));padding:20px 15px;text-align:center;border-bottom:2px solid rgba(0,217,255,0.3)}}
.banner-title{{font-size:2em;color:#00d9ff;text-shadow:0 0 20px rgba(0,217,255,0.6);font-weight:700;letter-spacing:1px;margin-bottom:5px}}
.banner-subtitle{{font-size:0.95em;color:rgba(255,255,255,0.7);margin-top:5px}}
.container{{max-width:1200px;margin:0 auto;padding:15px}}
.status{{display:inline-block;padding:6px 16px;background:rgba(0,255,127,0.15);border:2px solid #00ff7f;border-radius:20px;color:#00ff7f;font-size:0.85em;font-weight:600;margin:15px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin-bottom:20px}}
.card{{background:rgba(255,255,255,0.06);border:1px solid rgba(0,217,255,0.25);border-radius:12px;padding:20px;box-shadow:0 6px 25px rgba(0,0,0,0.4)}}
.card-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.card-title{{font-size:1.15em;color:#00d9ff;font-weight:600}}
.value{{font-size:1.4em;color:#00d9ff;font-weight:700}}
.input-box{{display:flex;gap:8px;margin-bottom:12px}}
.txt-input{{flex:1;background:rgba(255,255,255,0.08);border:1px solid rgba(0,217,255,0.3);border-radius:8px;padding:9px 12px;color:#fff;font-size:0.95em}}
.txt-input:focus{{outline:none;border-color:#00d9ff;background:rgba(0,217,255,0.12)}}
.apply{{background:#00d9ff;border:none;border-radius:8px;padding:9px 18px;color:#0f2027;font-weight:700;cursor:pointer;font-size:0.9em}}
.apply:active{{transform:scale(0.96)}}
input[type=range]{{-webkit-appearance:none;width:100%;height:7px;border-radius:4px;background:rgba(0,217,255,0.2);outline:none}}
input[type=range]::-webkit-slider-thumb{{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:#00d9ff;cursor:pointer;box-shadow:0 0 8px rgba(0,217,255,0.6)}}
input[type=range]::-moz-range-thumb{{width:18px;height:18px;border-radius:50%;background:#00d9ff;cursor:pointer;border:none}}
.info{{font-size:0.8em;color:rgba(255,255,255,0.5);margin-top:6px}}
.actions{{background:rgba(255,255,255,0.06);border:1px solid rgba(0,217,255,0.25);border-radius:12px;padding:20px;box-shadow:0 6px 25px rgba(0,0,0,0.4);margin-bottom:20px}}
.sec-title{{font-size:1.2em;color:#00d9ff;margin-bottom:15px;font-weight:600;text-align:center}}
.btn-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:18px}}
.btn-center{{display:flex;justify-content:center;margin-top:10px}}
.btn-calibrate{{padding:14px 40px;border-radius:10px;border:none;font-weight:700;font-size:1em;cursor:pointer;background:#ffa500;color:#fff;box-shadow:0 4px 15px rgba(255,165,0,0.4);transition:all 0.2s}}
.btn-calibrate:hover{{box-shadow:0 6px 20px rgba(255,165,0,0.6);transform:translateY(-2px)}}
.btn-calibrate:active{{transform:scale(0.96)}}
button{{padding:11px 14px;border-radius:9px;border:none;font-weight:600;font-size:0.9em;cursor:pointer;transition:transform 0.15s}}
button:active{{transform:scale(0.96)}}
.btn-pri{{background:#00d9ff;color:#0f2027}}
.btn-suc{{background:#00ff7f;color:#0f2027}}
.btn-warn{{background:#ffa500;color:#fff}}
.btn-dng{{background:#ff4757;color:#fff}}
@media (max-width:768px){{.banner-title{{font-size:1.6em}}.banner-subtitle{{font-size:0.85em}}.banner img{{max-height:180px}}.grid{{grid-template-columns:1fr}}.btn-calibrate{{padding:12px 30px;font-size:0.95em}}}}
</style></head><body>
<div class="banner">
<img src="/arnobot.jpeg" alt="Robotic Arm">
<div class="banner-text">
<h1 class="banner-title">🤖 ROBOTIC ARM CONTROL</h1>
<p class="banner-subtitle">Advanced 3-Axis Manipulation System</p>
</div>
</div>
<div class="container">
<div style="text-align:center"><div class="status">● SYSTEM ONLINE</div></div>
<div class="grid">
<div class="card"><div class="card-head"><span class="card-title">⚙️ Axis 1 (Base)</span><span class="value" id="v1">{s1}°</span></div>
<div class="input-box"><input type="number" class="txt-input" id="i1" placeholder="-175 to 175" min="-175" max="175">
<button class="apply" onclick="apply(1)">Apply</button></div>
<input type="range" min="-175" max="175" value="{s1}" id="s1" oninput="send(1,this.value)">
<div class="info">Range: -175° to 175°</div></div>
<div class="card"><div class="card-head"><span class="card-title">⚙️ Axis 2 (Shoulder)</span><span class="value" id="v2">{s2}°</span></div>
<div class="input-box"><input type="number" class="txt-input" id="i2" placeholder="Enter angle" min="{min_s2}" max="{max_s2}">
<button class="apply" onclick="apply(2)">Apply</button></div>
<input type="range" min="{min_s2}" max="{max_s2}" value="{s2}" id="s2" oninput="send(2,this.value)">
<div class="info" id="r2">Range: {min_s2}° to {max_s2}°</div></div>
<div class="card"><div class="card-head"><span class="card-title">⚙️ Axis 3 (Elbow)</span><span class="value" id="v3">{s3}°</span></div>
<div class="input-box"><input type="number" class="txt-input" id="i3" placeholder="Enter angle" min="{min_s3}" max="{max_s3}">
<button class="apply" onclick="apply(3)">Apply</button></div>
<input type="range" min="{min_s3}" max="{max_s3}" value="{s3}" id="s3" oninput="send(3,this.value)">
<div class="info" id="r3">Range: {min_s3}° to {max_s3}°</div></div></div>
<div class="actions"><h2 class="sec-title">⚡ Gripper Control</h2>
<div class="btn-grid"><button class="btn-suc" onclick="fetch('/gripper?action=open')">🖐️ Open Gripper</button>
<button class="btn-suc" onclick="fetch('/gripper?action=close')">✊ Close Gripper</button></div></div>
<div class="actions"><h2 class="sec-title">🎯 Calibration</h2>
<div class="btn-center">
<button class="btn-calibrate" onclick="cal()">🎯 Start Calibration</button>
</div></div>
<div class="actions"><h2 class="sec-title">💾 Position Memory</h2><div class="btn-grid">
<button class="btn-pri" onclick="fetch('/save_movement1')">💾 Save Position 1</button>
<button class="btn-pri" onclick="fetch('/save_movement2')">💾 Save Position 2</button>
<button class="btn-pri" onclick="fetch('/run1')">▶️ Go to Position 1</button>
<button class="btn-pri" onclick="fetch('/run2')">▶️ Go to Position 2</button></div></div>
<div class="actions"><h2 class="sec-title">🔄 Automation</h2><div class="btn-grid">
<button class="btn-dng" onclick="pickplace()" style="grid-column:1/-1">🔄 Execute Pick & Place</button></div></div></div>
<script>
function send(n,v){{fetch('/stepper?num='+n+'&angle='+v).then(r=>r.text()).then(()=>{{
if(n==2){{fetch('/get_range3').then(r=>r.json()).then(rng=>{{updateRange('s3','r3',rng,'v3','i3')}})}}
else if(n==3){{fetch('/get_range2').then(r=>r.json()).then(rng=>{{updateRange('s2','r2',rng,'v2','i2')}})}}
}});document.getElementById('v'+n).innerText=v+'°'}}
function updateRange(sid,rid,rng,vid,iid){{var slider=document.getElementById(sid);var input=document.getElementById(iid);
slider.min=rng.min;slider.max=rng.max;input.min=rng.min;input.max=rng.max;
var val=parseInt(slider.value);if(val<rng.min){{slider.value=rng.min;document.getElementById(vid).innerText=rng.min+'°'}}
else if(val>rng.max){{slider.value=rng.max;document.getElementById(vid).innerText=rng.max+'°'}}
document.getElementById(rid).innerText='Range: '+rng.min+'° to '+rng.max+'°'}}
function apply(n){{var input=document.getElementById('i'+n);var val=parseFloat(input.value);var slider=document.getElementById('s'+n);
var min=parseFloat(slider.min);var max=parseFloat(slider.max);if(isNaN(val)){{alert('Enter valid number');return}}
if(val<min||val>max){{alert('Value must be between '+min+' and '+max);return}}
slider.value=val;send(n,val);input.value=''}}
function cal(){{if(confirm('Start calibration? Arm will move to home position.')){{fetch('/calibrate').then(()=>{{
alert('Calibration in progress... Please wait. Page will reload in 3 seconds.');setTimeout(()=>location.reload(),3000)}})}}}}
function pickplace(){{if(confirm('Start Pick & Place automation?')){{fetch('/pickplace').then(()=>alert('Pick & Place sequence complete!'))}}}}
document.addEventListener('DOMContentLoaded',function(){{for(let i=1;i<=3;i++){{
document.getElementById('i'+i).addEventListener('keypress',e=>{{if(e.key==='Enter')apply(i)}})}}}});
</script></body></html>"""
    return html


if __name__ == "__main__":
    ap = create_access_point()

    gripper = Gripper()

    saved_movement_1 = []
    saved_movement_2 = []

    # instantiate joints (note: minDegree before maxDegree)
    joint1 = Joint(limit_pin=4, dir=9, pulse=11, minDegree=-175, maxDegree=175, maxPulse=3875, degreeToPulseRatio=3875 / 175,delay=600)
    joint2 = Joint(limit_pin=3, dir=7, pulse=13, minDegree=-20, maxDegree=70, maxPulse=3875, degreeToPulseRatio=2625 / 90, delay=800)
    joint3 = Joint(limit_pin=2, dir=14, pulse=15, minDegree=-90, maxDegree=90, maxPulse=3875, degreeToPulseRatio=2500 / 90,delay=600)

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)

    # ✅ Make listening socket non-blocking so main loop can keep updating steppers
    s.setblocking(False)

    print(f"Server running on http://{ap.ifconfig()[0]}:80")

    while True:
        # Always run stepper updates each loop iteration (non-blocking)
        stepper_update(joint1)
        stepper_update(joint2)
        stepper_update(joint3)

        # Try accept without blocking; if no client, continue loop and keep stepping
        cl = None
        try:
            cl, client_addr = s.accept()
        except OSError:
            cl = None

        if not cl:
            # short sleep to avoid 100% CPU spin; adjust if needed
            continue

        # Handle request (client connected)
        try:
            cl.settimeout(40)  # ms
            request = b""
            try:
                request = cl.recv(1024)
            except Exception as e:
                # if recv failed, close and continue
                print("recv error:", e)
                cl.close()
                continue

            if not request:
                cl.close()
                continue

            try:
                request = request.decode()
            except:
                request = str(request)

            parts = request.split(' ')
            if len(parts) < 2:
                cl.close()
                continue
            path = parts[1]
            print("Request:", path)

            # Serve image file
            if path.startswith('/arnobot.jpeg'):
                print('Serving image...')
                try:
                    with open('arnobot.jpeg', 'rb') as f:
                        f.seek(0, 2)
                        file_size = f.tell()
                        f.seek(0)
                        header = 'HTTP/1.0 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: {}\r\nConnection: close\r\n\r\n'.format(file_size)
                        cl.send(header.encode())
                        bytes_sent = 0
                        while True:
                            chunk = f.read(1024)
                            if not chunk:
                                break
                            cl.send(chunk)
                            bytes_sent += len(chunk)
                            gc.collect()
                        print(f'✓ Image served: {bytes_sent}/{file_size} bytes')
                except Exception as e:
                    print(f'Image error: {e}')
                    try:
                        cl.send(b'HTTP/1.0 404 Not Found\r\n\r\n')
                    except:
                        pass
                cl.close()
                continue

            # Stepper control (safe parsing)
            elif path.startswith('/stepper'):
                # Example path: /stepper?num=1&angle=45
                try:
                    q = path.split('?')[1]
                    parts_q = q.split('&')
                    num = int(parts_q[0].split('=')[1])   # ✅ int
                    angle = float(parts_q[1].split('=')[1])
                except Exception as e:
                    print("Bad stepper request:", e)
                    cl.send(b'HTTP/1.0 400 Bad Request\r\n\r\n')
                    cl.close()
                    continue

                if num == 1:
                    move_stepper(angle, joint1)
                elif num == 2:
                    solve_d3(angle)
                    move_stepper(angle, joint2)
                elif num == 3:
                    solve_d2(angle)
                    move_stepper(angle, joint3)

                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nOK')
                cl.close()
                continue


            elif path.startswith('/set_delay'):
                # Example path: /stepper?num=1&angle=45
                try:
                    q = path.split('?')[1]
                    parts_q = q.split('&')
                    num = int(parts_q[0].split('=')[1])   # ✅ int
                    delay = float(parts_q[1].split('=')[1])
                    if delay < 200:
                        delay = 200

                except Exception as e:
                    print("Bad stepper request:", e)
                    cl.send(b'HTTP/1.0 400 Bad Request\r\n\r\n')
                    cl.close()
                    continue

                if num == 1:
                    joint1.delay = delay
                elif num == 2:
                    joint2.delay = delay
                elif num == 3:
                    joint3.delay = delay

                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nOK')
                cl.close()
                continue

            # Gripper
            elif path.startswith('/gripper'):
                # expect /gripper?action=open or /gripper?action=close
                try:
                    action = path.split('=')[1]
                except:
                    action = ''
                if 'open' in action:
                    gripper.open()
                elif 'close' in action:
                    gripper.close()
                try:
                    cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')
                except:
                    pass
                cl.close()
                continue

            # Calibrate (blocking - keep behavior)
            elif path.startswith('/calibrate'):
                calibrate_steppers(joint1, joint2, joint3)
                try:
                    cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')
                except:
                    pass
                cl.close()
                continue

            # Run saved sequences
            elif path.startswith('/run1'):
                if saved_movement_1:
                    print("Running to Position 1...")
                    move_stepper(0, joint1)
                    move_stepper(0, joint2)
                    move_stepper(0, joint3)
                    time.sleep(1)
                    move_stepper(saved_movement_1[0], joint1)
                    move_stepper(saved_movement_1[1], joint2)
                    move_stepper(saved_movement_1[2], joint3)
                    print("✅ Position 1 reached")
                try:
                    cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')
                except:
                    pass
                cl.close()
                continue

            elif path.startswith('/run2'):
                if saved_movement_2:
                    print("Running to Position 2...")
                    move_stepper(0, joint1)
                    move_stepper(0, joint2)
                    move_stepper(0, joint3)
                    time.sleep(1)
                    move_stepper(saved_movement_2[0], joint1)
                    move_stepper(saved_movement_2[1], joint2)
                    move_stepper(saved_movement_2[2], joint3)
                    print("✅ Position 2 reached")
                try:
                    cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')
                except:
                    pass
                cl.close()
                continue

            elif path.startswith('/current_position'):

                cl.send(
                    b'HTTP/1.0 200 OK\r\n'
                    b'Content-Type: application/json\r\n'
                    b'Connection: close\r\n\r\n'
                    + current_position_json
                )

                cl.close()
                continue



            elif path.startswith('/save_movement1'):
                saved_movement_1 = (joint1.currentDegree, joint2.currentDegree, joint3.currentDegree)
                print("✅ Saved Movement 1:", saved_movement_1)
                cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')
                cl.close()
                continue

            elif path.startswith('/save_movement2'):
                saved_movement_2 =(joint1.currentDegree, joint2.currentDegree, joint3.currentDegree)
                print("✅ Saved Movement 2:", saved_movement_2)
                cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')
                cl.close()
                continue


            elif path.startswith('/favicon.ico'):
                try:
                    cl.send(b'HTTP/1.0 404 Not Found\r\n\r\n')
                except:
                    pass
                cl.close()
                continue

            # Main page - send in chunks
            else:
                response = web_page()
                send_response(cl, response)
                cl.close()

        except Exception as e:
            print("Error handling client:", e)
            try:
                cl.close()
            except:
                pass

        gc.collect()