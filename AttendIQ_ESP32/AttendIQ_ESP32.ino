/*
 * ============================================================
 *  AttendIQ — ESP32 TFT Firmware v4
 *  New flow: shows session info when idle,
 *  flashes student details when camera scans their QR.
 *
 *  Libraries: TFT_eSPI, ArduinoJson
 * ============================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>

// ── CONFIG ────────────────────────────────────────────────────
const char* WIFI_SSID   = "lala";
const char* WIFI_PASS   = "yoo";
const char* SERVER_IP   = "192.168.1.XXX";   // your PC's IP
const int   SERVER_PORT = 5000;
const int   POLL_MS     = 2000;   // poll every 2s for fast response
// ─────────────────────────────────────────────────────────────

TFT_eSPI tft = TFT_eSPI();

#define C_BG     TFT_BLACK
#define C_ACCENT 0x07FF    // Cyan
#define C_WHITE  TFT_WHITE
#define C_MUTED  0x4A49
#define C_GREEN  0x07E0
#define C_RED    0xF800
#define C_YELLOW 0xFFE0

String  lastSID      = "";
bool    lastActive   = false;
bool    lastFresh    = false;
String  lastRoll     = "";
unsigned long lastPoll = 0;

// ── SCREENS ───────────────────────────────────────────────────
void showBoot() {
  tft.fillScreen(C_BG);
  tft.setTextColor(C_ACCENT); tft.setTextSize(2);
  tft.setCursor(10, 30); tft.println("AttendIQ");
  tft.setTextSize(1); tft.setTextColor(C_MUTED);
  tft.setCursor(10, 58); tft.println("Smart Attendance");
  tft.setCursor(10, 72); tft.println("Initializing...");
}

void showIdle(String sid, String subj, String cls) {
  tft.fillScreen(C_BG);

  // Header
  tft.fillRect(0, 0, 160, 18, 0x0841);
  tft.setTextColor(C_ACCENT); tft.setTextSize(1);
  tft.setCursor(4, 5); tft.print("ATTENDIQ");
  tft.setTextColor(C_GREEN); tft.setCursor(108, 5); tft.print("LIVE");

  // Divider
  tft.drawFastHLine(0, 18, 160, 0x1082);

  // Subject block
  tft.setTextColor(C_MUTED); tft.setCursor(8, 28);
  tft.println("SUBJECT");
  tft.setTextColor(C_WHITE); tft.setCursor(8, 40);
  tft.println(subj.length() > 20 ? subj.substring(0,20) : subj);

  // Class block
  tft.setTextColor(C_MUTED); tft.setCursor(8, 58);
  tft.println("CLASS");
  tft.setTextColor(C_WHITE); tft.setCursor(8, 70);
  tft.println(cls.length() > 20 ? cls.substring(0,20) : cls);

  // Divider
  tft.drawFastHLine(8, 88, 144, 0x2104);

  // Waiting message
  tft.setTextColor(C_MUTED); tft.setCursor(8, 98);
  tft.println("Waiting for scan...");

  // Session ID
  tft.setTextColor(0x2945); tft.setCursor(8, 118);
  tft.print("ID: "); tft.print(sid);
}

void showScanned(String name, String roll, String dept, String year) {
  tft.fillScreen(C_BG);

  // Green success header
  tft.fillRect(0, 0, 160, 22, 0x0320);
  tft.setTextColor(C_GREEN); tft.setTextSize(1);
  tft.setCursor(8, 7); tft.print("✓ ATTENDANCE MARKED");

  // Big checkmark area
  tft.setTextColor(C_GREEN); tft.setTextSize(3);
  tft.setCursor(66, 28); tft.print("✓");

  // Student details
  tft.setTextSize(1);
  tft.setTextColor(C_MUTED); tft.setCursor(8, 68);
  tft.println("NAME");
  tft.setTextColor(C_WHITE); tft.setCursor(8, 80);
  // Truncate name if too long
  tft.println(name.length() > 20 ? name.substring(0,20) : name);

  tft.setTextColor(C_MUTED); tft.setCursor(8, 96);
  tft.println("ROLL NO");
  tft.setTextColor(C_ACCENT); tft.setCursor(8, 108);
  tft.println(roll);

  // Dept + year on one line
  tft.setTextColor(C_MUTED); tft.setCursor(8, 120);
  String info = dept + " · " + year;
  tft.println(info.length() > 22 ? info.substring(0,22) : info);
}

void showNoSession() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, 160, 18, 0x0841);
  tft.setTextColor(C_ACCENT); tft.setTextSize(1);
  tft.setCursor(4, 5); tft.print("ATTENDIQ");

  tft.setTextColor(C_MUTED); tft.setCursor(8, 36);
  tft.println("No active session.");
  tft.setCursor(8, 52); tft.println("Start one from the");
  tft.setCursor(8, 64); tft.println("teacher dashboard.");

  tft.drawFastHLine(8, 82, 144, 0x2104);
  tft.setCursor(8, 92); tft.println("Polling server...");
}

void showError(String msg) {
  tft.fillScreen(C_BG);
  tft.setTextColor(C_RED); tft.setCursor(10, 20); tft.println("Error");
  tft.setTextColor(C_MUTED); tft.setCursor(10, 38); tft.println(msg);
  tft.setCursor(10, 54); tft.println("Retrying...");
}

// ── WIFI ──────────────────────────────────────────────────────
void connectWiFi() {
  tft.fillScreen(C_BG);
  tft.setTextColor(C_ACCENT); tft.setTextSize(1);
  tft.setCursor(10, 10); tft.println("ATTENDIQ");
  tft.setTextColor(C_MUTED);
  tft.setCursor(10, 28); tft.print("Connecting WiFi...");

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int t = 0;
  while (WiFi.status() != WL_CONNECTED && t < 30) {
    delay(500); tft.print("."); t++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    tft.fillScreen(C_BG);
    tft.setTextColor(C_GREEN); tft.setCursor(10, 20);
    tft.println("WiFi Connected!");
    tft.setTextColor(C_MUTED); tft.setCursor(10, 36);
    tft.println(WiFi.localIP().toString());
    delay(1500);
    showNoSession();
  } else {
    tft.fillScreen(C_BG);
    tft.setTextColor(C_RED); tft.setCursor(10, 20);
    tft.println("WiFi FAILED");
    tft.setTextColor(C_MUTED); tft.setCursor(10, 36);
    tft.println("Check credentials");
  }
}

// ── SERVER POLL ───────────────────────────────────────────────
void pollServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/api/tft_status";
  http.begin(url); http.setTimeout(4000);
  int code = http.GET();

  if (code == 200) {
    String body = http.getString();
    DynamicJsonDocument doc(1024);
    if (deserializeJson(doc, body)) { http.end(); return; }

    bool   active    = doc["active"].as<bool>();
    bool   scanFresh = doc["scan_fresh"].as<bool>();
    String sid       = doc["session_id"] | "";
    String subj      = doc["subject"]    | "";
    String cls       = doc["class_name"] | "";

    if (!active) {
      if (lastActive) {
        showNoSession();
        lastActive = false; lastSID = ""; lastFresh = false;
      }
      http.end(); return;
    }

    lastActive = true;

    // New scan just came in
    if (scanFresh && !lastFresh) {
      JsonObject ls = doc["last_scanned"].as<JsonObject>();
      String name = ls["name"] | "Unknown";
      String roll = ls["roll"] | "—";
      String dept = ls["dept"] | "—";
      String year = ls["year"] | "—";
      showScanned(name, roll, dept, year);
      lastFresh = true;
      lastRoll  = roll;
    }

    // Scan expired — go back to idle
    if (!scanFresh && lastFresh) {
      showIdle(sid, subj, cls);
      lastFresh = false;
    }

    // New session started
    if (sid != lastSID) {
      showIdle(sid, subj, cls);
      lastSID   = sid;
      lastFresh = false;
    }

  } else {
    Serial.println("HTTP: " + String(code));
  }
  http.end();
}

// ── SETUP / LOOP ──────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(C_BG);
  showBoot();
  delay(800);
  connectWiFi();
}

void loop() {
  if (millis() - lastPoll >= POLL_MS) {
    lastPoll = millis();
    pollServer();
  }
}
