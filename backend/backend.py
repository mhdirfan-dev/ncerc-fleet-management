# ============================================================
#  FILE: edge/backend.py
#  PURPOSE: REST API backend for bus detection system
#  Framework: Flask
#  Endpoints: view logs, bus status, daily summary
#  Install: pip install flask flask-cors pymongo
# ============================================================

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import datetime
import os
import json
import subprocess
import threading

# Import our database module
from cont_database import (
    connect, disconnect, is_connected,
    save_detection, sync_backup,
    get_today_logs, get_logs_by_bus,
    get_logs_by_date, get_last_n_logs,
    get_bus_status, get_all_buses_today,
    update_status, clear_old_records
)

app = Flask(__name__)
CORS(app, origins=["https://ncerc-fleet-management.vercel.app"])
socketio = SocketIO(app, cors_allowed_origins="https://ncerc-fleet-management.vercel.app")

BUS_NUMBERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'bus_numbers.txt')

# ── Demo streaming state ──────────────────────────────────────
import queue as _queue
demo_frame_queue = _queue.Queue(maxsize=4)
demo_process     = None
demo_running     = False

# ──────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────
def load_official_buses():
    if not os.path.exists(BUS_NUMBERS_FILE):
        return []
    with open(BUS_NUMBERS_FILE) as f:
        return list(dict.fromkeys(
            ''.join(c for c in l.strip().upper() if c.isalnum())
            for l in f if l.strip()
        ))

# ──────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────

# ── Health check ──
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status"    : "ok",
        "database"  : "connected" if is_connected() else "disconnected",
        "timestamp" : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ── Today's logs ──
@app.route("/api/logs/today", methods=["GET"])
def logs_today():
    logs = get_today_logs()
    return jsonify({
        "date"  : datetime.datetime.now().strftime("%Y-%m-%d"),
        "count" : len(logs),
        "logs"  : logs
    })

# ── Logs by date ──
@app.route("/api/logs/date/<date_str>", methods=["GET"])
def logs_by_date(date_str):
    # date_str format: YYYY-MM-DD
    logs = get_logs_by_date(date_str)
    return jsonify({
        "date"  : date_str,
        "count" : len(logs),
        "logs"  : logs
    })

# ── Logs by bus number ──
@app.route("/api/logs/bus/<bus_number>", methods=["GET"])
def logs_by_bus(bus_number):
    logs = get_logs_by_bus(bus_number.upper())
    return jsonify({
        "bus_number" : bus_number.upper(),
        "count"      : len(logs),
        "logs"       : logs
    })

# ── Last N logs ──
@app.route("/api/logs/recent", methods=["GET"])
def recent_logs():
    n    = request.args.get("n", 20, type=int)
    logs = get_last_n_logs(n)
    return jsonify({
        "count" : len(logs),
        "logs"  : logs
    })

# ── Today's bus summary ──
@app.route("/api/summary/today", methods=["GET"])
def summary_today():
    buses    = get_all_buses_today()
    official = load_official_buses()
    summary  = []
    for bus in buses:
        summary.append({
            "bus_number"     : bus["_id"],
            "last_direction" : bus["last_direction"],
            "last_seen"      : bus["last_seen"],
            "total_events"   : bus["total_events"],
            "is_official"    : bus["_id"] in official
        })
    # Add buses not yet seen today
    seen_buses = {b["_id"] for b in buses}
    for official_bus in official:
        if official_bus not in seen_buses:
            summary.append({
                "bus_number"     : official_bus,
                "last_direction" : None,
                "last_seen"      : None,
                "total_events"   : 0,
                "is_official"    : True
            })
    return jsonify({
        "date"    : datetime.datetime.now().strftime("%Y-%m-%d"),
        "total"   : len(summary),
        "summary" : summary
    })

# ── Bus current status ──
@app.route("/api/bus/<bus_number>/status", methods=["GET"])
def bus_status(bus_number):
    status = get_bus_status(bus_number.upper())
    return jsonify({
        "bus_number" : bus_number.upper(),
        "status"     : status,
        "inside"     : status == "ENTRY",
        "timestamp"  : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ── All registered buses ──
@app.route("/api/buses", methods=["GET"])
def all_buses():
    official = load_official_buses()
    return jsonify({
        "count" : len(official),
        "buses" : official
    })

# ── Manual log entry (for testing) ──
@app.route("/api/logs/add", methods=["POST"])
def add_log():
    data       = request.json
    bus_number = data.get("bus_number", "").upper()
    direction  = data.get("direction", "ENTRY").upper()
    timestamp  = data.get("timestamp",
                          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if not bus_number:
        return jsonify({"error": "bus_number required"}), 400
    if direction not in ["ENTRY", "EXIT"]:
        return jsonify({"error": "direction must be ENTRY or EXIT"}), 400

    doc_id = save_detection(bus_number, direction, timestamp)
    if doc_id:
        return jsonify({
            "success"    : True,
            "bus_number" : bus_number,
            "direction"  : direction,
            "timestamp"  : timestamp
        })
    else:
        return jsonify({"error": "Failed to save"}), 500

# ── Entry count and exit count today ──
@app.route("/api/stats/today", methods=["GET"])
def stats_today():
    logs   = get_today_logs()
    entry  = sum(1 for l in logs if l["direction"] == "ENTRY")
    exit_c = sum(1 for l in logs if l["direction"] == "EXIT")
    buses  = len(set(l["bus_number"] for l in logs))
    return jsonify({
        "date"         : datetime.datetime.now().strftime("%Y-%m-%d"),
        "total_events" : len(logs),
        "entry_count"  : entry,
        "exit_count"   : exit_c,
        "unique_buses" : buses
    })

# ── Week logs ──
@app.route("/api/logs/week", methods=["GET"])
def logs_week():
    today = datetime.datetime.now()
    start = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    from cont_database import get_logs_by_date_range
    logs = get_logs_by_date_range(start, end)
    return jsonify({"logs": logs, "count": len(logs)})

# ── Month logs ──
@app.route("/api/logs/month", methods=["GET"])
def logs_month():
    today = datetime.datetime.now()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    from cont_database import get_logs_by_date_range
    logs = get_logs_by_date_range(start, end)
    return jsonify({"logs": logs, "count": len(logs)})

# ── Custom range logs ──
@app.route("/api/logs/range", methods=["GET"])
def logs_range():
    start = request.args.get("from", "")
    end   = request.args.get("to",   "")
    if not start or not end:
        return jsonify({"error": "from and to params required"}), 400
    from cont_database import get_logs_by_date_range
    logs = get_logs_by_date_range(start, end)
    return jsonify({"logs": logs, "count": len(logs)})
# ── Demo: start yolo_ocr.py subprocess ──
@app.route("/api/demo/start", methods=["POST"])
def start_demo():
    global demo_process, demo_running, demo_frame_queue
    data       = request.json or {}
    video_type = data.get("type", "entry")

    base = os.path.join(os.path.dirname(__file__), '..', 'ai_engine')
    if video_type == "entry":
        video_file = os.path.join(base, 'test_video1.MOV')
    else:
        video_file = os.path.join(base, 'test_video4.mov')

    if demo_running and demo_process and demo_process.poll() is None:
        return jsonify({"status": "already_running"})

    # clear old frames
    while not demo_frame_queue.empty():
        try: demo_frame_queue.get_nowait()
        except: break

    yolo_script = os.path.join(os.path.dirname(__file__),
                               '..', 'ai_engine', 'yolo_ocr.py')
    demo_process = subprocess.Popen(
        ["python", yolo_script, "--video", video_file, "--stream"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    def read_frames():
        import struct
        global demo_running
        try:
            while True:
                header = demo_process.stdout.read(4)
                if not header or len(header) < 4:
                    break
                size  = struct.unpack('>I', header)[0]
                data  = demo_process.stdout.read(size)
                if not data:
                    break
                try:
                    demo_frame_queue.put_nowait(data)
                except:
                    pass
        finally:
            demo_running = False
            demo_frame_queue.put_nowait(None)

    threading.Thread(target=read_frames, daemon=True).start()
    demo_running = True
    return jsonify({"status": "started", "video": video_type})


# ── Demo: MJPEG stream endpoint ──
@app.route("/api/demo/stream")
def demo_stream():
    def generate():
        while True:
            try:
                frame = demo_frame_queue.get(timeout=10)
                if frame is None:   # sentinel — video ended
                    break
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except:
                break
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ── Demo: stop ──
@app.route("/api/demo/stop", methods=["POST"])
def stop_demo():
    global demo_process, demo_running
    if demo_process:
        demo_process.terminate()
    demo_running = False
    return jsonify({"status": "stopped"})


# ── Demo: detection notify (called by yolo_ocr.py after each save) ──
@app.route("/api/detection/notify", methods=["POST"])
def detection_notify():
    data = request.json or {}
    socketio.emit('new_detection', {
        "bus_number": data.get("bus_number"),
        "direction":  data.get("direction"),
        "timestamp":  data.get("timestamp"),
        "date":       data.get("timestamp","").split(" ")[0],
        "time":       data.get("timestamp","").split(" ")[-1],
    })
    return jsonify({"status": "ok"})


# ── Socket.io — emit new detection to dashboard ──
def emit_new_detection(bus_number, direction, timestamp, date, time):


    """Call this from yolo_ocr.py after save_log() to push to dashboard."""
    socketio.emit('new_detection', {
        "bus_number": bus_number,
        "direction":  direction,
        "timestamp":  timestamp,
        "date":       date,
        "time":       time
    })


# ── Push alert from schedule_check.py to dashboard ──
@app.route("/api/alert/push", methods=["POST"])
def push_alert():
    data = request.json or {}
    # Emit to all connected dashboard browsers via Socket.IO
    socketio.emit('schedule_alert', {
        "window_label"  : data.get("window_label", ""),
        "direction"     : data.get("direction", ""),
        "missing_buses" : data.get("missing_buses", []),
        "missing_count" : data.get("missing_count", 0),
        "window_start"  : data.get("window_start", ""),
        "window_end"    : data.get("window_end", ""),
        "timestamp"     : data.get("timestamp", "")
    })
    print(f"[WS] Schedule alert pushed to dashboard: {data.get('missing_count',0)} missing buses")
    return jsonify({"success": True})

# ── Get recent alerts from MongoDB ──
@app.route("/api/alerts/recent", methods=["GET"])
def get_recent_alerts():
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb+srv://ncerc_admin:ncerc123@ncerc-fleet.utptozm.mongodb.net/?appName=ncerc-fleet", serverSelectionTimeoutMS=3000)
        col    = client["college_bus_system"]["dashboard_alerts"]
        alerts = list(col.find({}, {"_id": 0}).sort("datetime", -1).limit(20))
        return jsonify({"alerts": alerts, "count": len(alerts)})
    except Exception as e:
        return jsonify({"alerts": [], "count": 0, "error": str(e)})

# ── Get today's alerts ──
@app.route("/api/alerts/today", methods=["GET"])
def get_today_alerts():
    try:
        from pymongo import MongoClient
        import datetime
        client = MongoClient("mongodb+srv://ncerc_admin:ncerc123@ncerc-fleet.utptozm.mongodb.net/?appName=ncerc-fleet", serverSelectionTimeoutMS=3000)
        col    = client["college_bus_system"]["dashboard_alerts"]
        today  = datetime.datetime.now().strftime("%Y-%m-%d")
        alerts = list(col.find({"date": today}, {"_id": 0}).sort("datetime", -1))

        # Mark all unseen alerts as seen after dashboard fetches them
        col.update_many(
            {"date": today, "seen": False},
            {"$set": {"seen": True}}
        )
        return jsonify({"alerts": alerts, "count": len(alerts)})
    except Exception as e:
        return jsonify({"alerts": [], "count": 0})

# ── Get alerts for any specific date ──
@app.route("/api/alerts/date/<date_str>", methods=["GET"])
def get_alerts_by_date(date_str):
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb+srv://ncerc_admin:ncerc123@ncerc-fleet.utptozm.mongodb.net/?appName=ncerc-fleet", serverSelectionTimeoutMS=3000)
        col    = client["college_bus_system"]["dashboard_alerts"]
        alerts = list(col.find({"date": date_str}, {"_id": 0}).sort("datetime", -1))
        return jsonify({"alerts": alerts, "count": len(alerts), "date": date_str})
    except Exception as e:
        return jsonify({"alerts": [], "count": 0, "date": date_str})

# ── Count unseen alerts (for notification badge) ──
@app.route("/api/alerts/unseen", methods=["GET"])
def unseen_alerts():
    try:
        from pymongo import MongoClient
        import datetime
        client = MongoClient("mongodb+srv://ncerc_admin:ncerc123@ncerc-fleet.utptozm.mongodb.net/?appName=ncerc-fleet", serverSelectionTimeoutMS=3000)
        col    = client["college_bus_system"]["dashboard_alerts"]
        today  = datetime.datetime.now().strftime("%Y-%m-%d")
        count  = col.count_documents({"date": today, "seen": False})
        return jsonify({"unseen_count": count})
    except Exception as e:
        return jsonify({"unseen_count": 0})

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*50)
    print(" College Bus Detection — Backend API")
    print("="*50)

    # Connect to MongoDB
    if connect():
        sync_backup()
        clear_old_records(365)
        print("\n[API] Starting Flask server...")
        print("[API] Endpoints:")
        print("  GET  http://localhost:5000/api/health")
        print("  GET  http://localhost:5000/api/logs/today")
        print("  GET  http://localhost:5000/api/logs/date/2026-03-12")
        print("  GET  http://localhost:5000/api/logs/bus/KL08AF3035")
        print("  GET  http://localhost:5000/api/logs/recent?n=20")
        print("  GET  http://localhost:5000/api/summary/today")
        print("  GET  http://localhost:5000/api/stats/today")
        print("  GET  http://localhost:5000/api/buses")
        print("  GET  http://localhost:5000/api/bus/KL08AF3035/status")
        print("  POST http://localhost:5000/api/logs/add")
        print()
        socketio.run(app, host="0.0.0.0", port=5000, debug=False)
    else:
        print("[API] ❌ Cannot start — MongoDB not connected")
        print("[API] Start MongoDB first then run backend.py again")