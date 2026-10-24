"""
scanner.py — AttendIQ Laptop Camera QR Scanner
===============================================
Run this on the TEACHER'S LAPTOP alongside app.py.

    python scanner.py

It opens the laptop webcam, continuously scans for QR codes,
decodes student data, and POSTs to Flask to mark attendance.
The TFT display will then show the scanned student's info.

Requirements:
    pip install opencv-python pyzbar pillow
"""

import cv2
import json
import time
import requests
from pyzbar.pyzbar import decode

SERVER = "http://localhost:5000"
SCAN_COOLDOWN = 3   # seconds between same QR scans (avoid double-mark)

last_scanned = {}   # roll → timestamp

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam. Check camera connection.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("=" * 50)
    print("  AttendIQ QR Scanner — Running")
    print("  Press Q to quit")
    print("=" * 50)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Camera read failed.")
            break

        # Decode QR codes in frame
        codes = decode(frame)
        for code in codes:
            raw = code.data.decode('utf-8')

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue  # not our QR format

            # Must have 'sid' and 'r' (roll) keys
            if 'sid' not in data or 'r' not in data:
                continue

            roll = data['r']
            now  = time.time()

            # Cooldown — don't re-scan same roll within 3 seconds
            if roll in last_scanned and now - last_scanned[roll] < SCAN_COOLDOWN:
                continue

            last_scanned[roll] = now

            # Draw green box around QR on screen
            pts = code.polygon
            if len(pts) == 4:
                for i in range(4):
                    pt1 = (pts[i].x,           pts[i].y)
                    pt2 = (pts[(i+1)%4].x, pts[(i+1)%4].y)
                    cv2.line(frame, pt1, pt2, (0, 255, 0), 3)

            # Show name on screen
            name = data.get('n', 'Unknown')
            cv2.putText(frame, f"Marking: {name}",
                        (pts[0].x, pts[0].y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 255, 0), 2)

            # POST to Flask
            try:
                r = requests.post(f"{SERVER}/api/scan_result",
                                  json=data, timeout=3)
                result = r.json()
                if result.get('success'):
                    print(f"[✓] {result['msg']}")
                else:
                    print(f"[!] {result.get('msg', 'Unknown error')}")
            except Exception as e:
                print(f"[ERROR] Could not reach server: {e}")

        # Draw UI overlay
        cv2.putText(frame, "AttendIQ Scanner — Q to quit",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 229, 255), 2)

        # Show scan count
        cv2.putText(frame, f"Scanned: {len(last_scanned)}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (100, 200, 100), 1)

        cv2.imshow("AttendIQ — QR Scanner (press Q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Scanner stopped.")

if __name__ == '__main__':
    main()
