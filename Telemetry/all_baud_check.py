import serial
import time

PORT = "COM15"

# Common baud rates for RFD / SiK
baud_rates = [
     1200, 2400, 4800, 9600,
     19200, 38400, 57600,
     115200, 460800,
    1200000
]

print("Scanning COM16 for RFD response...\n")

for baud in baud_rates:
    print(f"Trying baud: {baud}")

    try:
        ser = serial.Serial(PORT, baud, timeout=1)

        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Guard time before +++
        time.sleep(2)

        # Send +++ WITHOUT newline
        ser.write(b"+++")
        time.sleep(1.5)

        response = ser.read_all().decode(errors="ignore")

        if response:
            print(f"Response after +++ at {baud}:")
            print(response)

        # Try ATI command
        ser.write(b"ATI\r\n")
        time.sleep(1)

        response = ser.read_all().decode(errors="ignore")

        if response:
            print(f"ATI Response at {baud}:")
            print(response)

        ser.close()

    except Exception as e:
        print(f"Error at {baud}: {e}")

    print("-" * 40)

print("\nScan complete.")