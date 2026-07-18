/*
  Fingerprint Attendance System - ESP32 Firmware (UNIFIED v2)
  ------------------------------------------------------------
  Hardware: ESP32, R307S fingerprint sensor, DS3231 RTC,
            0.91" OLED (SSD1306, I2C), Buzzer (via S8050 transistor)

  CHANGES FROM v1 (unified enroll/attendance):
  1. DELAY FIX: /api/device_mode + /api/active_session (two blocking
     HTTPS calls per poll cycle) merged into ONE call: /api/poll
     This removes one full TLS handshake + round-trip from every cycle.
  2. DELETE MODE added: mode == "DELETE" -> device deletes a template
     from the sensor via finger.deleteModel(id), reports back via
     /api/delete_result.
  3. FINGERPRINT ID ASSIGNMENT MOVED TO SERVER: previously the device
     computed the next free template ID itself via
     finger.getTemplateCount()+1 - this breaks once fingerprints are
     deleted from the middle of the sequence (ID collisions). Now the
     server sends enroll_fingerprint_id in the /api/poll response
     during ENROLLMENT mode, and the device stores the template under
     THAT id instead of computing its own.

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
const char* SERVER_HOST = "himasara.pythonanywhere.com"; // TODO: confirm - no trailing slash
const bool  USE_HTTPS   = true;

// ---- This device's fixed classroom/subject slot ----
const int TIMETABLE_ID = 7;   // CONFIRMED via DB: this device serves timetable_id=7

// ---- Demo mode ----
const bool DEMO_MODE = true;

// ---- Timing ----
const unsigned long POLL_INTERVAL_MS   = 4000;   // how often to check mode / active session
const unsigned long SCAN_COOLDOWN_MS   = 3000;   // pause after an attendance scan attempt
const unsigned long ENROLL_STEP_TIMEOUT_MS = 15000; // give up waiting for a finger during enrollment/delete

// ---- Pin mapping (ESP32 devkit, 38-pin) ----
#define FINGERPRINT_RX_PIN 16   // TODO: confirm - ESP32 pin wired to R307S TX
#define FINGERPRINT_TX_PIN 17   // TODO: confirm - ESP32 pin wired to R307S RX

#define I2C_SDA_PIN 21          // TODO: confirm
#define I2C_SCL_PIN 22          // TODO: confirm
#define OLED_WIDTH   128
#define OLED_HEIGHT  32
#define OLED_ADDRESS 0x3C

#define BUZZER_PIN 25           // TODO: confirm

// ===================================================================================

HardwareSerial fingerSerial(2);
Adafruit_Fingerprint finger(&fingerSerial);
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
RTC_DS3231 rtc;

unsigned long lastPollTime = 0;
int activeSessionId = -1;

// Mode state, refreshed every poll from /api/poll
String currentMode = "ATTENDANCE";   // "ATTENDANCE" / "ENROLLMENT" / "DELETE"

long enrollStudentId = -1;
String enrollStudentName = "";
int enrollFingerprintId = -1;        // server-assigned - NOT computed locally anymore

long deleteStudentId = -1;
int deleteFingerprintId = -1;

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
    pollServer();   // single merged call - was two calls before
  }

  if (currentMode == "ENROLLMENT" && enrollStudentId >= 0) {
    runEnrollmentFlow();
  } else if (currentMode == "DELETE" && deleteStudentId >= 0) {
    runDeleteFlow();
  } else if (currentMode == "ATTENDANCE") {
    runAttendanceFlow();
  } else {
    delay(300);
  }
}

// -----------------------------------------------------------------------------------
// ===================== MERGED POLL (delay fix) =====================
// -----------------------------------------------------------------------------------
// GET /api/poll?timetable_id=X  -> sets currentMode + session/enroll/delete state
// Replaces the old separate pollDeviceMode() + pollActiveSession() calls.
void pollServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST + "/api/poll";
  if (!DEMO_MODE) {
    url += "?timetable_id=" + String(TIMETABLE_ID);
  }

  http.begin(url);
  int httpCode = http.GET();

  if (httpCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<384> doc;
    DeserializationError err = deserializeJson(doc, payload);
    if (!err) {
      String mode = doc["mode"].as<String>();
      currentMode = mode;

      // reset all mode-specific state, then fill in what's relevant
      enrollStudentId = -1;
      deleteStudentId = -1;

      if (mode == "ENROLLMENT") {
        enrollStudentId = doc["enroll_student_id"].as<long>();
        enrollStudentName = doc["enroll_name"].isNull() ? "" : doc["enroll_name"].as<String>();
        enrollFingerprintId = doc["enroll_fingerprint_id"].as<int>();
      } else if (mode == "DELETE") {
        deleteStudentId = doc["delete_student_id"].as<long>();
        deleteFingerprintId = doc["delete_fingerprint_id"].as<int>();
      } else {
        // ATTENDANCE
        activeSessionId = doc["session_id"].isNull() ? -1 : doc["session_id"].as<int>();
      }
    } else {
      Serial.println("JSON parse error on /api/poll response");
    }
  } else {
    Serial.printf("/api/poll request failed, code=%d\n", httpCode);
  }

  http.end();
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

int tryReadFingerprint() {
  int p = finger.getImage();
  if (p != FINGERPRINT_OK) return -1;

  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) return -1;

  p = finger.fingerFastSearch();
  if (p != FINGERPRINT_OK) {
    showMessage("Not recognized", "Try again");
    beep(100);
    return -1;
  }

  return finger.fingerID;
}

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
// ===================== ENROLLMENT MODE =====================
// -----------------------------------------------------------------------------------
void runEnrollmentFlow() {
  showMessage("Enrollment Mode", enrollStudentName.length() ? enrollStudentName : String(enrollStudentId));

  if (enrollFingerprintId < 1) {
    reportEnrollResult(false, -1, "Server did not provide a valid fingerprint_id");
    return;
  }

  bool success = enrollFingerprintAtId(enrollFingerprintId);

  if (success) {
    showMessage("Enrolled OK", "id=" + String(enrollFingerprintId));
    beep(300);
    reportEnrollResult(true, enrollFingerprintId, "");
  } else {
    showMessage("Enroll failed", "Try again");
    beep(600);
    reportEnrollResult(false, -1, "Enrollment failed on device");
  }

  delay(1000);
}

// Standard Adafruit_Fingerprint two-scan enrollment sequence.
// `id` is now always server-assigned (see enrollFingerprintId above).
bool enrollFingerprintAtId(int id) {
  int p = -1;

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

  showMessage("Remove finger", "");
  delay(1500);
  p = 0;
  start = millis();
  while (p != FINGERPRINT_NOFINGER) {
    p = finger.getImage();
    if (millis() - start > ENROLL_STEP_TIMEOUT_MS) return false;
    delay(100);
  }

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

  p = finger.createModel();
  if (p != FINGERPRINT_OK) return false;

  p = finger.storeModel(id);
  if (p != FINGERPRINT_OK) return false;

  return true;
}

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
// ===================== DELETE MODE (new) =====================
// -----------------------------------------------------------------------------------
void runDeleteFlow() {
  showMessage("Delete Mode", "id=" + String(deleteFingerprintId));

  if (deleteFingerprintId < 1) {
    reportDeleteResult(false, "Server did not provide a valid fingerprint_id");
    return;
  }

  int p = finger.deleteModel(deleteFingerprintId);
  bool success = (p == FINGERPRINT_OK);

  if (success) {
    showMessage("Deleted OK", "id=" + String(deleteFingerprintId));
    beep(300);
    reportDeleteResult(true, "");
  } else {
    showMessage("Delete failed", "code " + String(p));
    beep(600);
    reportDeleteResult(false, "finger.deleteModel failed, code=" + String(p));
  }

  delay(1000);
}

// POST /api/delete_result  { student_id, success, message }
void reportDeleteResult(bool success, const String& message) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(USE_HTTPS ? "https://" : "http://") + SERVER_HOST + "/api/delete_result";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<192> reqDoc;
  reqDoc["student_id"] = deleteStudentId;
  reqDoc["success"] = success;
  if (message.length()) {
    reqDoc["message"] = message;
  }
  String requestBody;
  serializeJson(reqDoc, requestBody);

  int httpCode = http.POST(requestBody);
  if (httpCode != 200) {
    Serial.printf("delete_result POST failed, code=%d, body=%s\n", httpCode, http.getString().c_str());
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
