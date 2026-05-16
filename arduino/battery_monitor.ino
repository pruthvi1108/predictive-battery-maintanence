#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_INA219.h>

// --- Pin Definitions & Settings ---
#define ONE_WIRE_BUS 2
#define RELAY_PIN 7
#define TEMP_THRESHOLD 30.0

// --- Objects ---
LiquidCrystal_I2C lcd(0x27, 16, 2);
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
Adafruit_INA219 ina219;

void setup() {
  Serial.begin(9600);
  Wire.begin();

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  if (!ina219.begin()) {
    // Do NOT print here — ROS2 serial_node will skip "Failed" lines safely
    while (1) { delay(10); }
  }

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Initializing...");

  sensors.begin();
  delay(2000);
  lcd.clear();
}

void loop() {
  // --- 1. Read Sensor Data ---
  sensors.requestTemperatures();
  float tempC        = sensors.getTempCByIndex(0);
  float busVoltage   = ina219.getBusVoltage_V();
  float current_mA   = ina219.getCurrent_mA();

  // --- 2. Fan Control ---
  String fanStatus = "OFF";
  if (tempC >= TEMP_THRESHOLD) {
    digitalWrite(RELAY_PIN, HIGH);
    fanStatus = "ON";
  } else {
    digitalWrite(RELAY_PIN, LOW);
    fanStatus = "OFF";
  }

  // --- 3. LCD Display ---
  lcd.setCursor(0, 0);
  lcd.print("Temp : ");
  lcd.print(tempC, 1);
  lcd.print(" C    ");

  lcd.setCursor(0, 1);
  lcd.print("Volts: ");
  lcd.print(busVoltage, 2);
  lcd.print(" V    ");

  // --- 4. Serial Output ---
  // LINE A: Human-readable (for Arduino Serial Monitor / debugging)
  Serial.print("Temperature: ");
  Serial.print(tempC);
  Serial.print(" C  |  Battery: ");
  Serial.print(busVoltage);
  Serial.print(" V  |  Fan Draw: ");
  Serial.print(abs(current_mA));
  Serial.print(" mA  |  Fan Status: ");
  Serial.println(fanStatus);

  // LINE B: Clean CSV — parsed by ROS2 serial_node
  // Format: "voltage,current_mA,temperature"
  // serial_node reads this line and publishes to /bms/battery_data
  Serial.print("DATA:");
  Serial.print(busVoltage, 4);
  Serial.print(",");
  Serial.print(abs(current_mA), 4);
  Serial.print(",");
  Serial.println(tempC, 4);

  delay(1000);
}
