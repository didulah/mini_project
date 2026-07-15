/*
  Fingerprint Attendance System - ESP32 Firmware
  ------------------------------------------------
  Hardware: ESP32, R307S fingerprint sensor, DS3231 RTC,
            0.91" OLED (SSD1306, I2C), Buzzer (via S8050 transistor)

  Flow:
    1. Connect to WiFi.
    2. Every POLL_INTERVAL_MS, ask the server:
         GET /api/active_session?timetable_id=TIMETABLE_ID
       to find out if a lecturer has started today's session for
       *this* device's fixed subject/timetable slot.
    3. If a session is active, try to read a fingerprint.
    4. On a local match (against templates already stored on the
       R307S itself), POST the result to the server:
         POST /api/scan   { "fingerprint_id": X, "session_id": Y }
    5. Show the result on the OLED + short buzzer beep, then continue
       polling (won't re-mark the same student twice - server handles
       that, but we also cool down locally to avoid spamming requests).

  !! BEFORE FLASHING !!
  Everything under "USER CONFIG" below is a placeholder. Confirm each
  value against your actual wiring / network / deployment before
  uploading to the ESP32.

  Required libraries (Arduino Library Manager):
    - Adafruit Fingerprint Sensor Library
    - Adafruit SSD1306
    - Adafruit GFX Library
    - ArduinoJson (v6+)
    - RTClib (for DS3231) [only used for on-screen clock, optional]
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_Fingerprint.h>
#include <RTClib.h>

// ===================== USER CONFIG - CONFIRM BEFORE FLASHING =====================

// ---- WiFi ----
const char* WIFI_SSID     = "A06";       // TODO: confirm
const char* WIFI_PASSWORD = "88888888";   // TODO: confirm

// ---- Server ----
// PythonAnywhere free-tier apps are served over HTTPS only.
const char* SERVER_HOST = "himasara.pythonanywhere.com"; // TODO: confirm - no trailing slash
const bool  USE_HTTPS   = true;

// ---- This device's fixed classroom/subject slot ----
// Every physical device only ever serves ONE row in the `timetable` table.
// Look up the correct timetable_id from the deployed DB before flashing.
const int TIMETABLE_ID = 1;   // TODO: confirm - e.g. via /admin panel or DB

// ---- Timing ----
const unsigned long POLL_INTERVAL_MS   = 4000;   // how often to check for an active session
const unsigned long SCAN_COOLDOWN_MS   = 3000;   // pause after a scan attempt (success or fail)

// ---- Pin mapping (ESP32 devkit, 38-pin) ----
// R307S fingerprint sensor uses UART (TX/RX). Using ESP32 Serial2 here.
#define FINGERPRINT_RX_PIN 16   // TODO: confirm - ESP32 pin wired to R307S TX
#define FINGERPRINT_TX_PIN 17   // TODO: confirm - ESP32 pin wired to R307S RX

// OLED + DS3231 share the I2C bus (different addresses, no conflict)
#define I2C_SDA_PIN 21          // TODO: confirm
#define I2C_SCL_PIN 22          // TODO: confirm
#define OLED_WIDTH   128
#define OLED_HEIGHT  32         // change to 64 if your module is 128x64
#define OLED_ADDRESS 0x3C       // common default for 0.91" SSD1306 modules

// Buzzer driven through the S8050 transistor
#define BUZZER_PIN 25           // TODO: confirm

// ===================================================================================

HardwareSerial fingerSerial(2);
Adafruit_Fingerprint finger(&fingerSerial);
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
RTC_DS3231 rtc;

unsigned long lastPollTime = 0;
int activeSessionId = -1;   // -1 = no active session right now

// -----------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("OLED init failed - check wiring/address");
  }
  showMessage("Booting...", "");

  if (!rtc.begin()) {
    Serial.println("RTC not found - clock display will be skipped");
  }

  fingerSerial.begin(57600, SERIAL_8N1, FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN);
  finger.begin(57600);
  if (finger.verifyPassword()) {
    Serial.println("Fingerprint sensor found.");
  } else {
    Serial.println("Fingerprint sensor NOT found - check wiring.");
    showMessage("Sensor error", "Check wiring");
  }

  connectWiFi();
}

// -----------------------------------------------------------------------------------
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastPollTime >= POLL_INTERVAL_MS) {
    lastPollTime = now;
    pollActiveSession();
  }

  if (activeSessionId != -1) {
    showMessage("Session active", "Scan finger...");
    int fingerprintId = tryReadFingerprint();
    if (fingerprintId >= 0) {
      submitScan(fingerprintId, activeSessionId);
      delay(SCAN_COOLDOWN_MS);
    }
  } else {
    showMessage("Waiting for", "session to start");
    delay(500);
  }
}

// -----------------------------------------------------------------------------------
void connectWiFi() {
  showMessage("Connecting WiFi", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
    showMessage("WiFi connected", WiFi.localIP().toString());
    delay(1000);
  } else {
    Serial.println("\nWiFi connection failed - will retry in loop()");
    showMessage("WiFi failed", "Retrying...");
  }
}

// -----------------------------------------------------------------------------------
// GET /api/active_session?timetable_id=X
void pollActiveSession() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST +
               "/api/active_session?timetable_id=" + String(TIMETABLE_ID);

  http.begin(url);
  int httpCode = http.GET();

  if (httpCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, payload);
    if (!err) {
      if (doc["session_id"].isNull()) {
        activeSessionId = -1;
      } else {
        activeSessionId = doc["session_id"].as<int>();
      }
    } else {
      Serial.println("JSON parse error on active_session response");
    }
  } else {
    Serial.printf("active_session request failed, code=%d\n", httpCode);
  }

  http.end();
}

// -----------------------------------------------------------------------------------
// Returns the matched fingerprint template ID, or -1 if no match / no finger present.
int tryReadFingerprint() {
  int p = finger.getImage();
  if (p != FINGERPRINT_OK) {
    return -1;   // no finger on sensor, or read error - just try again next loop
  }

  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) {
    return -1;
  }

  p = finger.fingerFastSearch();
  if (p != FINGERPRINT_OK) {
    showMessage("Not recognized", "Try again");
    beep(100);
    return -1;
  }

  // finger.fingerID is the template ID stored on the sensor,
  // matching Student.fingerprint_id in the database.
  return finger.fingerID;
}

// -----------------------------------------------------------------------------------
// POST /api/scan  { "fingerprint_id": X, "session_id": Y }
void submitScan(int fingerprintId, int sessionId) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST + "/api/scan";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<128> reqDoc;
  reqDoc["fingerprint_id"] = fingerprintId;
  reqDoc["session_id"] = sessionId;
  String requestBody;
  serializeJson(reqDoc, requestBody);

  int httpCode = http.POST(requestBody);
  String responseBody = http.getString();

  if (httpCode == 200) {
    showMessage("Attendance", "marked!");
    beep(300);
  } else {
    Serial.printf("scan failed, code=%d, body=%s\n", httpCode, responseBody.c_str());
    showMessage("Scan failed", "code " + String(httpCode));
    beep(600);
  }

  http.end();
}

// -----------------------------------------------------------------------------------
void beep(int durationMs) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(durationMs);
  digitalWrite(BUZZER_PIN, LOW);
}

// -----------------------------------------------------------------------------------
void showMessage(const String& line1, const String& line2) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(line1);
  display.setCursor(0, 12);
  display.println(line2);
  display.display();
}
