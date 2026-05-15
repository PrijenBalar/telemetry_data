from machine import Pin
import time

# For Pico W, use 'WL_GPIO0' or initialize WiFi first (then use pico_led)
# If using the 'pico-w' MicroPython build and wifi is initialized:
# from picozero import pico_led
# pico_led.on()
# pico_led.off()

# Or, using machine.Pin with the correct constant:
led = Pin("WL_GPIO0", Pin.OUT) # This is the correct pin for Pico W

while True:
    led.value(1)  # Turn LED ON
    time.sleep(1)
    led.value(0)  # Turn LED OFF
    time.sleep(1)
