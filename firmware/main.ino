/*
  Fingerprint Attendance System - ESP32 Firmware (UNIFIED)
  ------------------------------------------------------------
  Hardware: ESP32, R307S fingerprint sensor, DS3231 RTC,
            0.91" OLED (SSD1306, I2C), Buzzer (via S8050 transistor)

  WHAT CHANGED FROM THE OLD TWO-SKETCH SETUP:
  This single sketch now replaces both the old "attendance-only" sketch
  and the separate "enrollment-only" sketch. The device asks the server
  which mode it should be in, every poll cycle:

      GET /api/device_mode

  - mode == "ATTENDANCE" (default / idle):
        Behaves EXACTLY like the old attendance sketch - unchanged:
          GET  /api/active_session?timetable_id=X
          POST /api/scan   { fingerprint_id, session_id }

  - mode == "ENROLLMENT":
        Server also sends enroll_student_id (+ enroll_name). Device runs
        the standard two-scan R307S enrollment routine, stores the new
        template on the sensor, then reports back:
          POST /api/enroll_result  { student_id, fingerprint_id, success }
        The server automatically flips mode back to ATTENDANCE after
        this - no manual re-flash or mode button needed on the device.

  No admin panel / physical button on the device is needed - the mode
  switch is entirely controlled from the Admin Panel web page
  (Start Enrollment / Cancel Enrollment buttons).

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
const int TIMETABLE_ID = 7;   // CONFIRMED via DB: this device serves timetable_id=7

// ---- Demo mode ----
// true  = ignore TIMETABLE_ID above, react to WHICHEVER session is
//         currently active anywhere in the system. Handy for a single
//         device testing several subjects during team demos without
//         re-flashing every time you switch which lecture you're testing.
// false = production behavior - only reacts to this device's fixed
//         TIMETABLE_ID slot. Use this once the device is permanently
//         assigned to one real classroom/subject.
// !! Two lecturers should NOT start sessions for different subjects at
// the same time while DEMO_MODE is true - the device can only follow one.
const bool DEMO_MODE = true;

// ---- Timing ----
const unsigned long POLL_INTERVAL_MS   = 4000;   // how often to check mode / active session
const unsigned long SCAN_COOLDOWN_MS   = 3000;   // pause after an attendance scan attempt
const unsigned long ENROLL_STEP_TIMEOUT_MS = 15000; // give up waiting for a finger during enrollment

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
int activeSessionId = -1;   // -1 = no active session right now (ATTENDANCE mode)

// Mode state, refreshed every poll from /api/device_mode
String currentMode = "ATTENDANCE";   // "ATTENDANCE" or "ENROLLMENT"
long enrollStudentId = -1;
String enrollStudentName = "";

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
    pollDeviceMode();

    // ATTENDANCE mode still needs its own session poll, exactly as before.
    if (currentMode == "ATTENDANCE") {
      pollActiveSession();
    }
  }

  if (currentMode == "ENROLLMENT" && enrollStudentId >= 0) {
    runEnrollmentFlow();
  } else if (currentMode == "ATTENDANCE") {
    runAttendanceFlow();
  } else {
    delay(300);
  }
}

// -----------------------------------------------------------------------------------
// ===================== ATTENDANCE MODE (unchanged behaviour) =====================
// -----------------------------------------------------------------------------------
void runAttendanceFlow() {
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

// GET /api/active_session?timetable_id=X  (param omitted when DEMO_MODE)
void pollActiveSession() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST + "/api/active_session";
  if (!DEMO_MODE) {
    url += "?timetable_id=" + String(TIMETABLE_ID);
  }

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
// ===================== ENROLLMENT MODE (new) =====================
// -----------------------------------------------------------------------------------

// GET /api/device_mode -> sets currentMode / enrollStudentId / enrollStudentName
void pollDeviceMode() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST + "/api/device_mode";
  http.begin(url);
  int httpCode = http.GET();

  if (httpCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, payload);
    if (!err) {
      String mode = doc["mode"].as<String>();
      if (mode == "ENROLLMENT") {
        currentMode = "ENROLLMENT";
        enrollStudentId = doc["enroll_student_id"].as<long>();
        enrollStudentName = doc["enroll_name"].isNull() ? "" : doc["enroll_name"].as<String>();
      } else {
        currentMode = "ATTENDANCE";
        enrollStudentId = -1;
        enrollStudentName = "";
      }
    } else {
      Serial.println("JSON parse error on device_mode response");
    }
  } else {
    Serial.printf("device_mode request failed, code=%d\n", httpCode);
  }

  http.end();
}

// Runs one full enrollment attempt (blocking - this is fine, since the
// admin is actively watching the Admin Panel page waiting for a result).
void runEnrollmentFlow() {
  showMessage("Enrollment Mode", enrollStudentName.length() ? enrollStudentName : String(enrollStudentId));

  int newId = getNextFreeTemplateId();
  if (newId < 0) {
    reportEnrollResult(false, -1, "Could not read sensor template count");
    return;
  }

  bool success = enrollFingerprintAtId(newId);

  if (success) {
    showMessage("Enrolled OK", "id=" + String(newId));
    beep(300);
    reportEnrollResult(true, newId, "");
  } else {
    showMessage("Enroll failed", "Try again");
    beep(600);
    reportEnrollResult(false, -1, "Enrollment failed on device");
  }

  // pollDeviceMode() on the next cycle will pick up the server's switch
  // back to ATTENDANCE mode automatically - no local state to reset here
  // beyond what reportEnrollResult / the next poll already handles.
  delay(1000);
}

// Uses the sensor's own template count as the next free slot ID.
// NOTE: assumes templates are only ever added sequentially through this
// system (never deleted directly on the sensor) - good enough for this
// project's scope. IDs start at 1.
int getNextFreeTemplateId() {
  if (finger.getTemplateCount() != FINGERPRINT_OK) {
    return -1;
  }
  return finger.templateCount + 1;
}

// Standard Adafruit_Fingerprint two-scan enrollment sequence.
bool enrollFingerprintAtId(int id) {
  int p = -1;

  // ---- First scan ----
  showMessage("Place finger", "(1st scan)");
  unsigned long start = millis();
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER) {
      if (millis() - start > ENROLL_STEP_TIMEOUT_MS) return false;
      delay(100);
      continue;
    }
    if (p != FINGERPRINT_OK) return false;
  }

  p = finger.image2Tz(1);
  if (p != FINGERPRINT_OK) return false;

  // ---- Require finger removal before second scan ----
  showMessage("Remove finger", "");
  delay(1500);
  p = 0;
  start = millis();
  while (p != FINGERPRINT_NOFINGER) {
    p = finger.getImage();
    if (millis() - start > ENROLL_STEP_TIMEOUT_MS) return false;
    delay(100);
  }

  // ---- Second scan ----
  showMessage("Place finger", "(2nd scan)");
  p = -1;
  start = millis();
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER) {
      if (millis() - start > ENROLL_STEP_TIMEOUT_MS) return false;
      delay(100);
      continue;
    }
    if (p != FINGERPRINT_OK) return false;
  }

  p = finger.image2Tz(2);
  if (p != FINGERPRINT_OK) return false;

  // ---- Combine into a model and store it ----
  p = finger.createModel();
  if (p != FINGERPRINT_OK) return false;   // e.g. FINGERPRINT_ENROLLMISMATCH - two scans didn't match

  p = finger.storeModel(id);
  if (p != FINGERPRINT_OK) return false;

  return true;
}

// POST /api/enroll_result  { student_id, fingerprint_id, success, message }
void reportEnrollResult(bool success, int fingerprintId, const String& message) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST + "/api/enroll_result";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<256> reqDoc;
  reqDoc["student_id"] = enrollStudentId;
  reqDoc["success"] = success;
  if (success) {
    reqDoc["fingerprint_id"] = fingerprintId;
  }
  if (message.length()) {
    reqDoc["message"] = message;
  }
  String requestBody;
  serializeJson(reqDoc, requestBody);

  int httpCode = http.POST(requestBody);
  if (httpCode != 200) {
    Serial.printf("enroll_result POST failed, code=%d, body=%s\n", httpCode, http.getString().c_str());
  }

  http.end();
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
