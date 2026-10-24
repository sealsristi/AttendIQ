# 📋 AttendIQ - Smart QR Attendance System

A QR-based classroom attendance system. Students fill a short form on their phone and get a
personal QR code. The teacher's laptop webcam scans it, attendance is marked automatically,
and an **ESP32 with a TFT display** shows the student's details live.

![AttendIQ dashboard](images/dashboard.png)
<!-- Add your screenshots: images/dashboard.png (teacher panel) and images/circuit.jpg (ESP32 + TFT) -->

## How it works

1. The teacher starts a session on the web dashboard. A session QR code and link appear.
2. Students open the link on their phone and enter their details.
3. The phone shows a **personal QR code** for that student.
4. The student holds it up to the teacher's laptop webcam.
5. `scanner.py` reads the QR and sends it to the Flask server, which saves the attendance.
6. The scanner window shows "Marking: name", the TFT display shows the student's details,
   and the dashboard updates live.

## Features

- One unique session ID per class, so old QR codes stop working when the session ends
- Duplicate roll numbers are blocked within a session
- Live attendance list on the teacher dashboard
- ESP32 + TFT display showing the session and the last scanned student (optional hardware)
- All data is stored locally in SQLite. No cloud and no account needed

## Tech used

Python · Flask · SQLite · OpenCV · pyzbar · ESP32 (Arduino C++) · TFT_eSPI · HTML / CSS / JavaScript

## Project structure

```
AttendIQ/
├── app.py                  ← Flask server (run this first)
├── scanner.py              ← Laptop webcam QR scanner (run this second)
├── requirements.txt        ← Python libraries
├── templates/
│   ├── teacher.html        ← Teacher dashboard
│   └── student.html        ← Student phone page
├── static/uploads/
└── AttendIQ_ESP32/
    └── AttendIQ_ESP32.ino  ← ESP32 firmware
```

`attendance.db` is created automatically the first time you run the server.

## Requirements

- Python 3.8 or newer
- A laptop or PC with a webcam
- A phone (for students)
- The PC, the phones and the ESP32 all on the **same Wi-Fi network**
- *Optional:* an ESP32 board and an ST7735 TFT display

## Setup

### 1. Download and install

```bash
git clone https://github.com/DebjitXD/AttendIQ.git
cd AttendIQ
pip install -r requirements.txt
```

On Linux, also run `sudo apt install libzbar0`.

### 2. Start the server

```bash
python app.py
```

The server runs on port 5000.

### 3. Start the QR scanner (open a second terminal)

```bash
python scanner.py
```

A webcam window opens. Press **Q** to quit.

`scanner.py` talks to the server at `http://localhost:5000`, so run it on the **same PC** as `app.py`.

### 4. Allow network access

If Windows asks about the firewall the first time you run the server, click **Allow access**.
Without it, student phones cannot reach the server.

## How to use

### Teacher

1. Open `http://localhost:5000` in a browser **on the PC that runs the server**.
2. Enter the **college name, class name and subject**.
3. Click **Start Session**. A session QR code and a link appear.
4. Show the QR on the screen (or copy and share the link). Attendance appears live in the table.
5. Click **End Session** when class is over.

### Student

1. Scan the session QR (or open the link) on your phone.
2. Enter your **name, roll number, section, year and department**.
3. Your personal QR code appears. Turn your screen brightness up.
4. Hold it steady in front of the teacher's laptop camera.
5. When your name appears on the scanner window and the dashboard, you are marked present.

## ESP32 display setup (optional)

The system works without the ESP32. It only adds a live display.

### Libraries (Arduino IDE → Library Manager)

- `TFT_eSPI` by Bodmer
- `ArduinoJson` (version 6)

### TFT_eSPI configuration

Open `Documents/Arduino/libraries/TFT_eSPI/User_Setup.h` and set:

```cpp
#define ST7735_DRIVER
#define TFT_WIDTH  128
#define TFT_HEIGHT 160
#define TFT_CS     5
#define TFT_DC     2
#define TFT_RST    4
#define TFT_MOSI   23
#define TFT_SCLK   18
```

### Wiring

| TFT pin | ESP32 pin |
|---|---|
| VCC | 3.3V |
| GND | GND |
| CS | GPIO 5 |
| RESET | GPIO 4 |
| A0 / DC | GPIO 2 |
| SDA / MOSI | GPIO 23 |
| SCK | GPIO 18 |
| LED / BL | 3.3V |

![Circuit](images/circuit.jpg)

### Configure and upload

1. Open `AttendIQ_ESP32/AttendIQ_ESP32.ino` in the Arduino IDE.
2. Edit these three lines:

   ```cpp
   const char* WIFI_SSID   = "YOUR_WIFI_NAME";
   const char* WIFI_PASS   = "YOUR_WIFI_PASSWORD";
   const char* SERVER_IP   = "192.168.1.XXX";   // your PC's IP address
   ```

3. Find your PC's IP address: on Windows open Command Prompt, type `ipconfig`, and look for **IPv4 Address**.
4. Select the board **ESP32 Dev Module**, choose your COM port, and click **Upload**.
5. Open the Serial Monitor at **115200 baud** to see connection messages.

The ESP32 asks the server for updates every 2 seconds. It shows the active session and the last student scanned.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Teacher dashboard |
| GET | `/student?sid=...` | Student page for a session |
| POST | `/api/start_session` | Start a session and get its link and QR |
| POST | `/api/end_session` | End the active session |
| GET | `/api/session_status` | Live attendance list for the dashboard |
| GET | `/api/tft_status` | ESP32 polls this to update the display |
| GET | `/api/validate_session` | Check whether a session ID is still active |
| POST | `/api/generate_qr` | Create a student's personal QR code |
| POST | `/api/scan_result` | Scanner sends decoded student data here |
| GET | `/api/attendance_data` | Get saved attendance records |
| GET | `/api/all_sessions` | List all past sessions |

## Troubleshooting

| Problem | Fix |
|---|---|
| Phone can't open the link | Phone and PC must be on the same Wi-Fi. Allow Python through the firewall |
| Session link shows the wrong address | Open the teacher dashboard on the PC that runs `app.py` and check that the PC is connected to Wi-Fi |
| QR not detected | Increase phone brightness, hold steady, and keep the whole QR inside the camera view |
| Webcam does not open | Close other apps using the camera (Zoom, Meet). The scanner uses camera 0 |
| `pyzbar` / zbar error | Windows: reinstall with `pip install pyzbar`. Linux: `sudo apt install libzbar0` |
| "Could not reach server" in the scanner | Start `app.py` first, and run both on the same PC |
| ESP32 stuck on "Connecting" | Check the Wi-Fi name and password. ESP32 supports 2.4 GHz Wi-Fi only |
| TFT blank or wrong colours | Recheck the wiring and the `User_Setup.h` pins and driver |
| "Roll already marked" | That roll number is already recorded in the current session |

## Notes

- This is a demo / development setup. `app.py` runs with `debug=True`, so turn it off for real deployment.
- Attendance data is saved in `attendance.db` on your machine. Do not upload that file to GitHub.

## Future improvements

- Face recognition with OpenCV
- Export attendance to Excel / CSV
- Cloud sync with Firebase
- SMS / email alerts

## Team

- **Sristi Seal** - [@sealsristi](https://github.com/sealsristi)
- **Sristi Seal** - [@sealsristi](https://github.com/sealsristi)

## License

Released under the MIT License. See [LICENSE](LICENSE).
