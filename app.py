from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3, os, uuid, qrcode, base64, json, time, socket
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
DB = 'attendance.db'

# Global scanner state (shared between Flask and scanner.py via API)
scanner_state = {
    "active":        False,
    "session_id":    None,
    "subject":       None,
    "class_name":    None,
    "college":       None,
    "last_scanned":  None,
    "last_scan_time": 0,
}

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                college    TEXT,
                class_name TEXT,
                subject    TEXT,
                start_time TEXT,
                end_time   TEXT,
                active     INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                name       TEXT,
                roll       TEXT,
                section    TEXT,
                year       TEXT,
                dept       TEXT,
                subject    TEXT,
                timestamp  TEXT,
                UNIQUE(session_id, roll)
            );
        """)

init_db()

def get_active_session():
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM sessions WHERE active=1 ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

def get_local_ip():
    """Find this PC's Wi-Fi/LAN address so student phones can reach the server"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # open a small network socket
    try:
        s.connect(("8.8.8.8", 80))     # nothing is sent; this just picks the active network
        return s.getsockname()[0]      # our own address, e.g. 192.168.1.105
    except Exception:
        return "127.0.0.1"             # fallback if there is no network
    finally:
        s.close()                      # always close the socket

# ─────────────────────────────────────────────
# TEACHER PANEL
# ─────────────────────────────────────────────
@app.route('/')
def teacher_panel():
    return render_template('teacher.html')

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    with get_db() as db:
        db.execute("UPDATE sessions SET active=0, end_time=? WHERE active=1",
                   [datetime.now().isoformat()])
    sid = str(uuid.uuid4())[:8].upper()
    with get_db() as db:
        db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,1)",
                   [sid, data['college'], data['class_name'],
                    data['subject'], datetime.now().isoformat(), None])
    scanner_state.update({
        "active": True, "session_id": sid,
        "subject": data['subject'], "class_name": data['class_name'],
        "college": data['college'], "last_scanned": None,
    })
    url = f"http://{get_local_ip()}:5000/student?sid={sid}"   # link students will open
    qr = qrcode.make(url)                                     # turn the link into a QR image
    buf = BytesIO()                                           # temporary memory buffer
    qr.save(buf, format="PNG")                                # save the QR image into it
    qr_b64 = base64.b64encode(buf.getvalue()).decode()        # convert to text for the web page
    return jsonify({"session_id": sid, "url": url, "qr_b64": qr_b64})

@app.route('/api/end_session', methods=['POST'])
def end_session():
    with get_db() as db:
        db.execute("UPDATE sessions SET active=0, end_time=? WHERE active=1",
                   [datetime.now().isoformat()])
    scanner_state.update({"active": False, "session_id": None, "last_scanned": None})
    return jsonify({"status": "ended"})

@app.route('/api/session_status')
def session_status():
    sess = get_active_session()
    if not sess:
        return jsonify({"active": False})
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM attendance WHERE session_id=? ORDER BY timestamp DESC",
            [sess['session_id']]
        ).fetchall()
    return jsonify({
        "active": True, "session": sess,
        "records": [dict(r) for r in rows],
        "last_scanned": scanner_state.get("last_scanned")
    })

@app.route('/api/all_sessions')
def all_sessions():
    with get_db() as db:
        rows = db.execute("SELECT * FROM sessions ORDER BY start_time DESC").fetchall()
    return jsonify([dict(r) for r in rows])

# ─────────────────────────────────────────────
# ESP32 / TFT STATUS
# ─────────────────────────────────────────────
@app.route('/api/tft_status')
def tft_status():
    """ESP32 polls this every 2s to update TFT display"""
    sess = get_active_session()
    if not sess:
        return jsonify({"active": False})
    scan_age = time.time() - scanner_state.get("last_scan_time", 0)
    return jsonify({
        "active":       True,
        "session_id":   sess['session_id'],
        "subject":      sess['subject'],
        "class_name":   sess['class_name'],
        "last_scanned": scanner_state["last_scanned"] if scan_age < 6 else None,
        "scan_fresh":   scan_age < 6,
    })

# ─────────────────────────────────────────────
# STUDENT FORM & QR GENERATION
# ─────────────────────────────────────────────
@app.route('/student')
def student_page():
    sid = request.args.get('sid', '')
    return render_template('student.html', sid=sid)

@app.route('/api/validate_session')
def validate_session():
    sid = request.args.get('sid')
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM sessions WHERE session_id=? AND active=1", [sid]
        ).fetchone()
    if not row:
        return jsonify({"valid": False, "msg": "Session expired or invalid"})
    return jsonify({"valid": True, "subject": row['subject'],
                    "class_name": row['class_name']})

@app.route('/api/generate_qr', methods=['POST'])
def generate_qr():
    """Student submits form → server generates QR with their data"""
    data = request.json
    sid  = data.get('session_id', '')

    # Validate session
    with get_db() as db:
        sess = db.execute(
            "SELECT * FROM sessions WHERE session_id=? AND active=1", [sid]
        ).fetchone()
    if not sess:
        return jsonify({"success": False, "msg": "Session expired."})

    # Check duplicate
    with get_db() as db:
        dup = db.execute(
            "SELECT id FROM attendance WHERE session_id=? AND roll=?",
            [sid, data.get('roll', '')]
        ).fetchone()
    if dup:
        return jsonify({"success": False,
                        "msg": f"Roll {data.get('roll')} already marked."})

    # Compact JSON payload inside QR
    payload = json.dumps({
        "sid": sid,
        "n":   data.get('name', ''),
        "r":   data.get('roll', ''),
        "sec": data.get('section', ''),
        "yr":  data.get('year', ''),
        "d":   data.get('dept', ''),
        "sub": sess['subject'],
    }, separators=(',', ':'))

    # Generate QR — large box_size so laptop camera can read it easily
    qr = qrcode.QRCode(
        version=None, box_size=10, border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_M
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({"success": True, "qr_b64": b64,
                    "name": data.get('name'), "roll": data.get('roll')})

# ─────────────────────────────────────────────
# SCANNER CALLBACK (called by scanner.py)
# ─────────────────────────────────────────────
@app.route('/api/scan_result', methods=['POST'])
def scan_result():
    """scanner.py calls this when laptop camera reads a student QR"""
    data = request.json
    sid  = data.get('sid')
    roll = data.get('r')

    with get_db() as db:
        sess = db.execute(
            "SELECT * FROM sessions WHERE session_id=? AND active=1", [sid]
        ).fetchone()
    if not sess:
        return jsonify({"success": False, "msg": "Session expired."})

    with get_db() as db:
        dup = db.execute(
            "SELECT id FROM attendance WHERE session_id=? AND roll=?",
            [sid, roll]
        ).fetchone()
    if dup:
        return jsonify({"success": False,
                        "msg": f"Roll {roll} already marked."})

    ts = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO attendance
               (session_id,name,roll,section,year,dept,subject,timestamp)
               VALUES (?,?,?,?,?,?,?,?)""",
            [sid, data.get('n'), roll, data.get('sec'),
             data.get('yr'), data.get('d'), data.get('sub'), ts]
        )

    scanner_state['last_scanned'] = {
        "name": data.get('n'), "roll": roll,
        "dept": data.get('d'), "year": data.get('yr'),
    }
    scanner_state['last_scan_time'] = time.time()
    print(f"[✓] Marked: {data.get('n')} | {roll} | {ts}")
    return jsonify({"success": True, "msg": f"Marked: {data.get('n')}"})

@app.route('/api/attendance_data')
def attendance_data():
    sess_id = request.args.get('session_id')
    with get_db() as db:
        if sess_id:
            rows = db.execute(
                "SELECT * FROM attendance WHERE session_id=? ORDER BY timestamp DESC",
                [sess_id]).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM attendance ORDER BY timestamp DESC").fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    os.makedirs('static/uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
