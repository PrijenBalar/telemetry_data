"""
Laptop Telemetry Receiver
Receives JSON line packets from UGV via telemetry radio on laptop's USB port.
Parses and displays: bot telemetry, mission waypoints, heartbeat
"""

import json
import serial
import time
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG  — change port to your laptop's COM/ttyUSB
# ─────────────────────────────────────────
SERIAL_PORT = "COM15"        # Windows: "COM15"  |  Linux: "/dev/ttyUSB0"
BAUD_RATE   = 460800

# ─────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────

def print_telemetry(data: dict):
    print("  ┌─── Bot Telemetry ──────────────────")
    print(f"  │  Position  X: {data.get('x')}  Y: {data.get('y')}")
    print(f"  │  GPS       Lat: {data.get('lat')}  Lon: {data.get('long')}")
    print(f"  │  GPS Fix : {data.get('gps_fix')}    Satellites: {data.get('sat')}")
    print(f"  │  Yaw     : {data.get('yaw')}°")
    print(f"  │  Velocity: Vx={data.get('vx')}")
    print(f"  │  Battery : {data.get('batv')} V")
    print(f"  │  Uptime  : {data.get('uptime_ms')} ms")
    print(f"  │  Sigma   : σx={data.get('s_x')}  σy={data.get('s_y')}")
    print(f"  │  Telem Hz: {data.get('hz')}")
    print("  └────────────────────────────────────")

def print_waypoints(waypoints: list):
    if not waypoints:
        print("  [WAYPOINTS] No active mission waypoints")
        return
    print(f"  ┌─── Waypoints ({len(waypoints)}) ─────────────────")
    for wp in waypoints:
        label = f"  ({wp.get('label')})" if wp.get('label') else ""
        print(f"  │  [{wp.get('seq'):>3}] Lat:{wp.get('lat')}  Lon:{wp.get('lon')}  Alt:{wp.get('alt')}m{label}")
    print("  └────────────────────────────────────")

def print_packet(packet: dict, raw_line: str, pkt_count: int, last_ts: str):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    ts  = packet.get("ts", "N/A")
    bot_id = packet.get("bot_id", "N/A")
    data   = packet.get("data")
    waypoints = packet.get("waypoints", [])

    # Detect heartbeat (no data change, just ts bumped)
    tag = "HB " if data is None else "PKT"

    print(f"\n{'═'*52}")
    print(f"  [{now}]  #{pkt_count}  [{tag}]")
    print(f"  Bot ID : {bot_id}")
    print(f"  Server : {ts}")

    if data:
        print_telemetry(data)

    if waypoints:
        print_waypoints(waypoints)

    if not data and not waypoints:
        print("  [HEARTBEAT] Link alive — no payload change")

# ─────────────────────────────────────────
#  STATS
# ─────────────────────────────────────────

class Stats:
    def __init__(self):
        self.total       = 0
        self.heartbeats  = 0
        self.data_pkts   = 0
        self.parse_errors= 0
        self.start_time  = time.monotonic()
        self.last_rx     = None

    def print(self):
        elapsed = time.monotonic() - self.start_time
        rate = self.total / elapsed if elapsed > 0 else 0
        print(f"\n{'─'*52}")
        print(f"  STATS  uptime: {elapsed:.1f}s  avg rate: {rate:.2f} pkt/s")
        print(f"  Total   : {self.total}")
        print(f"  Data    : {self.data_pkts}")
        print(f"  HB      : {self.heartbeats}")
        print(f"  Errors  : {self.parse_errors}")
        if self.last_rx:
            print(f"  Last RX : {self.last_rx}")
        print(f"{'─'*52}")

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────

def main():
    stats = Stats()
    buffer = b""

    print("=" * 52)
    print("  UGV Telemetry Receiver")
    print(f"  Port: {SERIAL_PORT}  Baud: {BAUD_RATE}")
    print("=" * 52)

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"  Serial opened successfully\n")

        while True:
            # ── Read all available bytes ──────────
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue

            buffer += chunk

            # ── Split on newline (one JSON per line) ──
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()

                if not line:
                    continue

                stats.total += 1
                stats.last_rx = datetime.now().strftime("%H:%M:%S")

                # ── Parse JSON ────────────────────
                try:
                    packet = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    stats.parse_errors += 1
                    print(f"  [PARSE ERR #{stats.parse_errors}] {e}")
                    print(f"  Raw: {line[:80]}")
                    continue

                # ── Count type ────────────────────
                if packet.get("data") is not None:
                    stats.data_pkts += 1
                else:
                    stats.heartbeats += 1

                # ── Display ───────────────────────
                print_packet(packet, line, stats.total, stats.last_rx)

                # ── Stats every 20 packets ────────
                if stats.total % 20 == 0:
                    stats.print()

    except serial.SerialException as e:
        print(f"\n  [SERIAL ERROR] {e}")
        print(f"  Check: is {SERIAL_PORT} correct? Is device connected?")

    except KeyboardInterrupt:
        print("\n\n  Stopped by user.")

    finally:
        stats.print()
        if "ser" in locals() and ser.is_open:
            ser.close()
            print("  Serial port closed.")

if __name__ == "__main__":
    main()