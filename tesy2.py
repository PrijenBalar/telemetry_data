// -------------------- Pin
definitions - -------------------
constexpr
uint32_t
UART0_TX = 16;
constexpr
uint32_t
UART0_RX = 17;

constexpr
uint32_t
UART1_TX = 4;
constexpr
uint32_t
UART1_RX = 5;

constexpr
uint32_t
DIG_PINS[] = {3, 2, 19, 18};
constexpr
uint32_t
RELAY_PINS[] = {12, 13, 14, 15};

constexpr
uint32_t
ADC_VBAT = 26;
constexpr
uint32_t
ADC_IBAT = 27;

constexpr
uint32_t
LED_PIN = 25;

// -------------------- Power
module
constants - -------------------
constexpr
float
ADC_REF_VOLT = 3.3;
constexpr
float
ADC_MAX = 4095.0;

constexpr
float
VBAT_SCALE = 18.0;
constexpr
float
ISENSE_ZERO = 2.5;
constexpr
float
ISENSE_SCALE = 0.066;
float
vBat;
// -------------------- DATA
values - -------------------
int
v1 = 0, v2 = 0, v3 = 0, v4 = 0;
int
l1 = 0, l2 = 0, l3 = 0, l4 = 0;

// -------------------- Serial
buffer - -------------------
String
serial2Line = "";

static
unsigned
long
last_debug = 0;

long
int
limit_one = 0;
bool
limit_one_trigger = false;

long
int
limit_two = 0;
bool
limit_two_trigger = false;

int
pwm1 = 19;
int
dir1 = 20;

int
pwm2 = 10;
int
dir2 = 11;

bool
connected = false;

// -------------------- Setup - -------------------
void
setup()
{

for (uint8_t i = 0; i < 4; i++) {
    pinMode(DIG_PINS[i], INPUT_PULLUP);
pinMode(RELAY_PINS[i], OUTPUT);
digitalWrite(RELAY_PINS[i], HIGH);
}

pinMode(pwm2, OUTPUT);
pinMode(dir2, OUTPUT);


pinMode(pwm1, OUTPUT);
pinMode(dir1, OUTPUT);
digitalWrite(pwm1, LOW);
digitalWrite(dir1, LOW);
digitalWrite(pwm2, LOW);
digitalWrite(dir2, LOW);


Serial.begin(57600);

Serial1.setTX(UART0_TX);
Serial1.setRX(UART0_RX);
Serial1.begin(57600);

Serial2.setTX(UART1_TX);
Serial2.setRX(UART1_RX);
Serial2.begin(250000);



pinMode(LED_PIN, OUTPUT);
digitalWrite(LED_PIN, HIGH);

Serial.println("Pico system ready (single-reader mode)");
// delay(5000);
}

// -------------------- Loop - -------------------
void
loop()
{
    handleSerial2(); // ONE
place
reads
Serial2
readAndPrintIO();
if (connected)
{
    controlRelays();
}
sendData();
}

void
sendData()
{

if (millis() - last_debug > 100)
{
    last_debug = millis();

Serial2.println();
Serial2.print("DATA:");
Serial2.print(l3);
Serial2.print(" ");
Serial2.print(l2);
Serial2.print(" ");
Serial2.print(l1);
Serial2.print(" ");
Serial2.print(vBat);
Serial2.println(" ");
}
}

// -------------------- Serial2
handler - -------------------
void
handleSerial2()
{
while (Serial2.available()) {
char c = Serial2.read();

// Forward everything
Serial1.write(c);

// Line buffering
if (c == '\n') {
processLine(serial2Line);
serial2Line = "";
} else if (c != '\r') {
serial2Line += c;
}
}
}

// -------------------- Line
processor - -------------------
void
processLine(const
String & line) {
if (line.startsWith("DATA:")) {
sscanf(line.c_str(), "DATA:%d %d %d %d", & v1, & v2, & v3, & v4);

Serial.print("Decoded DATA: ");
Serial.print(v1);
Serial.print(", ");
Serial.print(v2);
Serial.print(", ");
Serial.print(v3);
Serial.print(", ");
Serial.println(v4);
// if (millis() - start_time > 3000){
// connected = true;
//}
if (v1 == 1 & & v2 == 1 & & v3 == 1 & & v4 == 1 )
{
// start_time = millis();
connected = false;
}
else {
connected = true;
}

}

}

// -------------------- IO + Power
print - -------------------
void
readAndPrintIO()
{
l1 = digitalRead(DIG_PINS[3]);
l2 = digitalRead(DIG_PINS[2]);
l3 = digitalRead(DIG_PINS[1]);
l4 = digitalRead(DIG_PINS[0]);

int
adcV = analogRead(ADC_VBAT);
int
adcI = analogRead(ADC_IBAT);

float
vSense = (adcV * ADC_REF_VOLT) / ADC_MAX;
float
iSense = (adcI * ADC_REF_VOLT) / ADC_MAX;

vBat = vSense * VBAT_SCALE;
float
iBat = (iSense - ISENSE_ZERO) / ISENSE_SCALE;

// Serial.print("| VBAT:");
// Serial.print(vBat, 2);
// Serial.print("V IBAT:");
Serial.print(millis() - limit_one);
Serial.print("A ");
Serial.print(millis() - limit_two);
Serial.print("A ");

Serial.print("| DATA:");
Serial.print(v1);
Serial.print(",");
Serial.print(v2);
Serial.print(",");
Serial.print(v3);
Serial.print(",");
Serial.println(v4);
}

// -------------------- Relay
control - -------------------
void
controlRelays()
{
// digitalWrite(RELAY_PINS[0], v1 == 0 ? HIGH: LOW);
digitalWrite(RELAY_PINS[1], v2 == 0 ? HIGH: LOW);
digitalWrite(RELAY_PINS[2], v1 == 0 ? HIGH: LOW);
// digitalWrite(RELAY_PINS[3], v4 == 1 ? HIGH: LOW);

if (v4 == 0) {
digitalWrite(pwm1, LOW);
digitalWrite(dir1, LOW);
limit_one = millis();

} else if (v4 == 1) {

if (l4 == 0 | | limit_one_trigger == true) {
limit_one_trigger = true;
digitalWrite(pwm1, LOW);
digitalWrite(dir1, LOW);

if (l4 != 0){
analogWrite(pwm1, 80);
digitalWrite(dir1, HIGH);
}

} else {

analogWrite(pwm1, 120);
digitalWrite(dir1, HIGH);
}
limit_one = millis();

} else {

limit_one_trigger = false;
if (millis() - limit_one < 3050) {
analogWrite(pwm1, 120);
digitalWrite(dir1, LOW);
} else {
digitalWrite(pwm1, LOW);
digitalWrite(dir1, LOW);
}
}

if (v3 == 0) {
digitalWrite(pwm2, LOW);
digitalWrite(dir2, LOW);
limit_two = millis();

} else if (v3 == 2) {

if (l3 == 0 | | limit_two_trigger == true) {
limit_two_trigger = true;
digitalWrite(pwm2, LOW);
digitalWrite(dir2, LOW);

if (l3 != 0){
analogWrite(pwm2, 80);
digitalWrite(dir2, LOW);
}

} else {

analogWrite(pwm2, 120);
digitalWrite(dir2, LOW);
}
limit_two = millis();

} else {

limit_two_trigger = false;
if (millis() - limit_two < 3050) {
analogWrite(pwm2, 120);
digitalWrite(dir2, HIGH);
} else {
digitalWrite(pwm2, LOW);
digitalWrite(dir2, LOW);
}
}

}