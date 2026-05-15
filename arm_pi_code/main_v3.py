import network
import socket
import time
from machine import Pin
import machine
import utime
import json
import gc

delay = 400

# Import DNS Server for captive portal
try:
    from microDNSSrv import MicroDNSSrv
    DNS_AVAILABLE = True
except:
    DNS_AVAILABLE = False
    print("⚠️ DNS server not available")

# Access Point credentials
AP_SSID = 'ARMOBOT'
AP_PASSWORD = '12345678'


class Gripper:
    def __init__(self):
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
    def __init__(self, dir, pulse, maxDegree, minDegree, maxPulse, degreeToPulseRatio):
        self.dirPin = Pin(dir, Pin.OUT)
        self.pulsePin = Pin(pulse, Pin.OUT)
        self.maxDegree = maxDegree
        self.minDegree = minDegree
        self.degreeToPulseRatio = degreeToPulseRatio
        self.maxPulse = maxPulse
        self.currentDegree = 0

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

default_p1 = [-50.0, 50.0, -20.0]
default_p2 = [40.0, 30.0, -30.0]

continuous_run = False

min_s2 = -20
max_s2 = 70
min_s3 = -90
max_s3 = 90

import math

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


# Limit switches
limit_switch_1 = Pin(4, Pin.IN, Pin.PULL_UP)
limit_switch_2 = Pin(3, Pin.IN, Pin.PULL_UP)
limit_switch_3 = Pin(2, Pin.IN, Pin.PULL_UP)

# Global limit state
limit_triggered = False
limit_trigger_time = 0


def any_limit_triggered():
    """Check if any limit switch is currently active (HIGH = triggered with PULL_UP)"""
    return (limit_switch_1.value() == 1 or
            limit_switch_2.value() == 1 or
            limit_switch_3.value() == 1)


def step_motor(steps, dirPin, pulPin, direction, delay_step=delay):
    """Step motor with per-step limit switch checking. Stops immediately on trigger."""
    global limit_triggered, limit_trigger_time
    dirPin.value(1 if direction else 0)
    for _ in range(steps):
        # Stop if limit already triggered before this call
        if limit_triggered:
            print("⚠️ Movement blocked — previous limit still active.")
            return
        # Check live switch state each step
        if any_limit_triggered():
            limit_triggered = True
            limit_trigger_time = time.ticks_ms()
            print("🛑 Limit triggered! Stopping motor immediately.")
            return
        pulPin.value(1)
        time.sleep_us(delay_step)
        pulPin.value(0)
        time.sleep_us(delay_step)


def move_stepper(target_degree, joint: Joint):
    """Move a joint to target_degree. Silently blocked if limit_triggered."""
    global limit_triggered
    if limit_triggered:
        print("⚠️ Movement blocked — limit switch lockout active.")
        return

    target_degree = max(min(target_degree, joint.maxDegree), joint.minDegree)
    degree_delta = target_degree - joint.currentDegree
    pulse_delta = int(abs(degree_delta) * joint.degreeToPulseRatio)

    if pulse_delta == 0:
        return

    direction = degree_delta > 0
    step_motor(abs(pulse_delta), joint.dirPin, joint.pulsePin, direction)

    # Only update position if we were not stopped by a limit
    if not limit_triggered:
        joint.currentDegree = target_degree
    print(f"Joint moved to: {joint.currentDegree}°")


def handle_limit_recovery():
    """
    Called every main loop tick.
    - If limit_triggered and 10 seconds have elapsed → auto-calibrate and reset.
    """
    global limit_triggered, limit_trigger_time

    if not limit_triggered:
        return

    elapsed = time.ticks_diff(time.ticks_ms(), limit_trigger_time)
    if elapsed >= 10000:  # 10 seconds
        print("⏳ 10 sec elapsed. Starting auto-recalibration...")
        calibrate_steppers(joint1, joint2, joint3)
        limit_triggered = False
        limit_trigger_time = 0
        print("✅ Limit reset. System ready.")


def calibrate_steppers(joint1: Joint, joint2: Joint, joint3: Joint):
    """
    Non-blocking concurrent calibration of all 3 joints.
    Each joint goes to its limit switch then backs off to zero position.
    """
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
    pulse_delay_1 = pulse_delay_2 = pulse_delay_3 = 400

    print("🔧 Calibrating steppers...")

    while not (done1 and done2 and done3):
        now = time.ticks_us()

        # --- Joint 1 ---
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

        # --- Joint 2 ---
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

        # --- Joint 3 ---
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
    """Send HTTP response in chunks to avoid EIO errors."""
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


def pick_place():
    """Execute pick and place sequence. Blocked if limit triggered."""
    global saved_movement_1, saved_movement_2
    if not saved_movement_1 or not saved_movement_2:
        print("❌ Save Position 1 and Position 2 first")
        return

    if limit_triggered:
        print("⚠️ Pick & Place blocked — limit switch lockout active.")
        return

    print("▶️ Moving to Position 1")
    move_stepper(saved_movement_1[0], joint1)
    solve_d3(saved_movement_1[1])
    move_stepper(saved_movement_1[1], joint2)
    solve_d2(saved_movement_1[2])
    move_stepper(saved_movement_1[2], joint3)
    time.sleep(1)
    gripper.open()
    time.sleep(1)
    gripper.close()
    time.sleep(1)

    if limit_triggered:
        print("⚠️ Limit triggered during Position 1 move. Aborting.")
        return

    print("▶️ Moving to Position 2")
    move_stepper(saved_movement_2[0], joint1)
    solve_d3(saved_movement_2[1])
    move_stepper(saved_movement_2[1], joint2)
    solve_d2(saved_movement_2[2])
    move_stepper(saved_movement_2[2], joint3)
    time.sleep(1)
    gripper.open()
    time.sleep(1)
    gripper.close()
    time.sleep(1)
    print("✅ Pick and Place Complete")


def pick_place_default():
    """Execute default pick and place for continuous mode."""
    global limit_triggered
    if limit_triggered:
        return

    print("▶️ Moving to Default Position 1")
    move_stepper(default_p1[0], joint1)
    solve_d3(default_p1[1])
    move_stepper(default_p1[1], joint2)
    solve_d2(default_p1[2])
    move_stepper(default_p1[2], joint3)
    time.sleep(1)
    gripper.open()
    time.sleep(1)
    gripper.close()
    time.sleep(1)

    if limit_triggered:
        return

    print("▶️ Moving to Default Position 2")
    move_stepper(default_p2[0], joint1)
    solve_d3(default_p2[1])
    move_stepper(default_p2[1], joint2)
    solve_d2(default_p2[2])
    move_stepper(default_p2[2], joint3)
    time.sleep(1)
    gripper.open()
    time.sleep(1)
    gripper.close()
    time.sleep(1)
    print("✅ Default Pick and Place Complete")


def web_page():
    s1 = int(joint1.currentDegree)
    s2 = int(joint2.currentDegree)
    s3 = int(joint3.currentDegree)

    # Show lockout status on page
    limit_status_html = ""
    if limit_triggered:
        elapsed = time.ticks_diff(time.ticks_ms(), limit_trigger_time)
        remaining = max(0, (10000 - elapsed) // 1000)
        limit_status_html = f'<div class="limit-alert">🛑 LIMIT SWITCH TRIGGERED — Auto-calibration in {remaining}s. All movement blocked.</div>'

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
.limit-alert{{background:rgba(255,71,87,0.2);border:2px solid #ff4757;border-radius:10px;padding:14px 18px;color:#ff4757;font-weight:700;font-size:1em;text-align:center;margin-bottom:18px;animation:pulse 1s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.6}}}}
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
{limit_status_html}
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
<div class="actions"><h2 class="sec-title">🔄 Automation</h2>
<div class="btn-grid">
<button class="btn-dng" onclick="pickplace()">🔄 Execute Pick &amp; Place</button>
<button class="btn-warn" onclick="fetch('/start_continuous')">▶️ Start Continuous Run</button>
<button class="btn-dng" onclick="fetch('/stop_continuous')">⏹️ Stop Continuous Run</button>
</div></div>
</div>
<script>
function send(n,v){{fetch('/stepper?num='+n+'&angle='+v).then(r=>r.text()).then(t=>{{
if(t.startsWith('LIMIT')){{alert(t);return;}}
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
alert('Calibration in progress... Page will reload in 3 seconds.');setTimeout(()=>location.reload(),3000)}})}}}}
function pickplace(){{if(confirm('Start Pick & Place automation?')){{fetch('/pickplace').then(r=>r.text()).then(t=>alert(t))}}}}
// Auto-refresh page every 5 sec so limit status updates
setInterval(()=>location.reload(), 5000);
document.addEventListener('DOMContentLoaded',function(){{for(let i=1;i<=3;i++){{
document.getElementById('i'+i).addEventListener('keypress',e=>{{if(e.key==='Enter')apply(i)}})}}}});
</script></body></html>"""
    return html


# ─────────────────────────── MOTOR COMMAND PATHS ────────────────────────────
MOTOR_PATHS = ['/stepper', '/run1', '/run2', '/pickplace', '/start_continuous']


def is_motor_path(path):
    return any(path.startswith(p) for p in MOTOR_PATHS)


def send_limit_blocked(cl):
    """Send a plain-text blocked response when limit is active."""
    elapsed = time.ticks_diff(time.ticks_ms(), limit_trigger_time)
    remaining = max(0, (10000 - elapsed) // 1000)
    msg = f'LIMIT TRIGGERED — Movement blocked. Auto-calibration in {remaining}s.'.encode()
    cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\n')
    cl.send(msg)


# ──────────────────────────────── MAIN ──────────────────────────────────────
if __name__ == "__main__":
    ap = create_access_point()

    gripper = Gripper()

    joint1 = Joint(dir=9,  pulse=11, minDegree=-175, maxDegree=175, maxPulse=3875, degreeToPulseRatio=3875/175)
    joint2 = Joint(dir=7,  pulse=13, minDegree=-20,  maxDegree=70,  maxPulse=3875, degreeToPulseRatio=2625/90)
    joint3 = Joint(dir=14, pulse=15, minDegree=-90,  maxDegree=90,  maxPulse=3875, degreeToPulseRatio=2500/90)

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    s.setblocking(False)   # ← KEY: non-blocking so recovery loop runs every tick
    print(f"Server running on http://{ap.ifconfig()[0]}:80")

    while True:
        # ── Handle incoming HTTP request (non-blocking) ──────────────────────
        cl = None
        try:
            cl, addr = s.accept()
            cl.settimeout(5.0)
            request = cl.recv(1024).decode()
            path = request.split(' ')[1]
            print("Request:", path)

            # ── Serve image ─────────────────────────────────────────────────
            if path.startswith('/arnobot.jpeg'):
                try:
                    with open('arnobot.jpeg', 'rb') as f:
                        f.seek(0, 2)
                        file_size = f.tell()
                        f.seek(0)
                        header = f'HTTP/1.0 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: {file_size}\r\nConnection: close\r\n\r\n'
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
                    cl.send(b'HTTP/1.0 404 Not Found\r\n\r\n')

            # ── Block all motor commands if limit is triggered ───────────────
            elif limit_triggered and is_motor_path(path):
                send_limit_blocked(cl)

            # ── Stepper control ─────────────────────────────────────────────
            elif path.startswith('/stepper'):
                parts = path.split('?')[1].split('&')
                num = int(parts[0].split('=')[1])
                angle = int(parts[1].split('=')[1])
                if num == 1:
                    move_stepper(angle, joint1)
                elif num == 2:
                    solve_d3(angle)
                    move_stepper(angle, joint2)
                elif num == 3:
                    solve_d2(angle)
                    move_stepper(angle, joint3)
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nOK')

            elif path.startswith('/get_range3'):
                response = '{{"min":{},"max":{}}}'.format(min_s3, max_s3)
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
                cl.send(response.encode())

            elif path.startswith('/get_range2'):
                response = '{{"min":{},"max":{}}}'.format(min_s2, max_s2)
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
                cl.send(response.encode())

            elif path.startswith('/gripper'):
                action = path.split('=')[1]
                if action == 'open':
                    gripper.open()
                elif action == 'close':
                    gripper.close()
                cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')

            elif path.startswith('/calibrate'):
                calibrate_steppers(joint1, joint2, joint3)
                cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')

            elif path.startswith('/save_movement1'):
                saved_movement_1.clear()
                saved_movement_1.extend([joint1.currentDegree, joint2.currentDegree, joint3.currentDegree])
                print("✓ Position 1 saved:", saved_movement_1)
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nPosition 1 Saved')

            elif path.startswith('/save_movement2'):
                saved_movement_2.clear()
                saved_movement_2.extend([joint1.currentDegree, joint2.currentDegree, joint3.currentDegree])
                print("✓ Position 2 saved:", saved_movement_2)
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nPosition 2 Saved')

            elif path.startswith('/run1'):
                if saved_movement_1 and not limit_triggered:
                    print("Running to Position 1...")
                    move_stepper(0, joint1)
                    move_stepper(0, joint2)
                    move_stepper(0, joint3)
                    time.sleep(1)
                    move_stepper(saved_movement_1[0], joint1)
                    solve_d3(saved_movement_1[1])
                    move_stepper(saved_movement_1[1], joint2)
                    solve_d2(saved_movement_1[2])
                    move_stepper(saved_movement_1[2], joint3)
                    print("✅ Position 1 reached")
                cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')

            elif path.startswith('/run2'):
                if saved_movement_2 and not limit_triggered:
                    print("Running to Position 2...")
                    move_stepper(0, joint1)
                    move_stepper(0, joint2)
                    move_stepper(0, joint3)
                    time.sleep(1)
                    move_stepper(saved_movement_2[0], joint1)
                    solve_d3(saved_movement_2[1])
                    move_stepper(saved_movement_2[1], joint2)
                    solve_d2(saved_movement_2[2])
                    move_stepper(saved_movement_2[2], joint3)
                    print("✅ Position 2 reached")
                cl.send(b'HTTP/1.0 200 OK\r\n\r\nOK')

            elif path.startswith('/pickplace'):
                pick_place()
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nPick Place Done')

            elif path.startswith('/start_continuous'):
                continuous_run = True
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nContinuous Run Started')

            elif path.startswith('/stop_continuous'):
                continuous_run = False
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\nContinuous Run Stopped')

            elif path.startswith('/favicon.ico'):
                cl.send(b'HTTP/1.0 404 Not Found\r\n\r\n')

            else:
                # Main page
                response = web_page()
                send_response(cl, response)

        except OSError as e:
            # errno 11 = EAGAIN: no connection available on non-blocking socket — totally normal
            if e.args[0] != 11:
                print("Socket error:", e)
        except Exception as e:
            print("Request handling error:", e)
        finally:
            if cl:
                try:
                    cl.close()
                except:
                    pass

        # ── Continuous run (only when not in limit lockout) ──────────────────
        if continuous_run and not limit_triggered:
            pick_place_default()
            time.sleep(2)

        # ── Limit recovery check — runs every loop tick ──────────────────────
        handle_limit_recovery()

        gc.collect()
        time.sleep_ms(50)  # Yield — keeps loop ~20Hz without burning CPU




