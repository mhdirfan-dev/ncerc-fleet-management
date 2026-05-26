# ============================================================
#  FILE: edge/schedule_check.py
#  PURPOSE: Monitors two daily time windows.
#
#  HOW IT WORKS (answer to confusion):
#  ─────────────────────────────────────────────────────────
#  This program can be started ANY time of day.
#  It checks REAL DATA from MongoDB for TODAY.
#
#  MORNING CHECK  (triggers once, after 09:00):
#    → Looks at MongoDB for buses that had ENTRY today
#      between 07:00 and 09:00
#    → Compares with bus_numbers.txt
#    → Buses NOT found in database = MISSING
#    → Sends Telegram + dashboard alert with missing list
#
#  EVENING CHECK  (triggers once, after 18:00):
#    → Looks at MongoDB for buses that had EXIT today
#      between 16:00 and 18:00
#    → Same comparison and alert
#
#  So even if you start at 20:00 — it will immediately
#  trigger the morning check AND evening check using
#  real data already saved in MongoDB today.
# ============================================================

import time
import datetime
import os
import requests
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# ──────────────────────────────────────────────────────────────
#  TELEGRAM CONFIGURATION
# ──────────────────────────────────────────────────────────────
import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS  = [os.environ.get("TELEGRAM_CHAT_ID", "")]

# ──────────────────────────────────────────────────────────────
#  SCHEDULE WINDOWS
# ──────────────────────────────────────────────────────────────
MORNING_START      = "07:00"
MORNING_END        = "09:00"
EVENING_START      = "16:00"
EVENING_END        = "18:00"

# ──────────────────────────────────────────────────────────────
#  OTHER CONFIG
# ──────────────────────────────────────────────────────────────
BUS_NUMBERS_FILE   = os.path.join(os.path.dirname(__file__), '..', 'config', 'bus_numbers.txt')
CHECK_INTERVAL_SEC = 60

MONGO_URI          = "mongodb+srv://ncerc_admin:ncerc123@ncerc-fleet.utptozm.mongodb.net/?appName=ncerc-fleet"
DATABASE_NAME      = "college_bus_system"
DETECTIONS_COL     = "bus_detections"
ALERTS_COL         = "dashboard_alerts"   # NEW: stores alerts for dashboard

BACKEND_URL        = "http://localhost:5000"  # backend.py URL for dashboard push

# ──────────────────────────────────────────────────────────────
#  MONGODB
# ──────────────────────────────────────────────────────────────
_client     = None
_detections = None
_alerts     = None

def connect_db():
    global _client, _detections, _alerts
    try:
        _client     = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _detections = _client[DATABASE_NAME][DETECTIONS_COL]
        _alerts     = _client[DATABASE_NAME][ALERTS_COL]
        print("[DB] ✅ Connected to MongoDB")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"[DB] ❌ Connection failed: {e}")
        return False

def is_connected():
    try:
        if _client:
            _client.admin.command("ping")
            return True
    except Exception:
        pass
    return False

# ──────────────────────────────────────────────────────────────
#  LOAD OFFICIAL BUS LIST
# ──────────────────────────────────────────────────────────────
def load_official_buses():
    if not os.path.exists(BUS_NUMBERS_FILE):
        print(f"[WARNING] {BUS_NUMBERS_FILE} not found.")
        return []
    with open(BUS_NUMBERS_FILE) as f:
        buses = [
            ''.join(c for c in line.strip().upper() if c.isalnum())
            for line in f if line.strip()
        ]
    seen, result = set(), []
    for b in buses:
        if b and b not in seen:
            seen.add(b)
            result.append(b)
    return result

# ──────────────────────────────────────────────────────────────
#  GET BUSES DETECTED IN A WINDOW  (reads TODAY's data)
# ──────────────────────────────────────────────────────────────
def get_buses_detected(direction, window_start, window_end):
    """
    Queries MongoDB for buses detected TODAY in the given
    direction between window_start and window_end.

    This is why running the program in the evening still
    correctly checks morning data — it queries the real
    database records from today.
    """
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    today   = ist_now.strftime("%Y-%m-%d")
    start_ts = f"{today} {window_start}:00"
    end_ts   = f"{today} {window_end}:00"

    records = _detections.find({
        "direction" : direction,
        "date"      : today,
        "timestamp" : {"$gte": start_ts, "$lte": end_ts}
    })
    return {r["bus_number"] for r in records}

# ──────────────────────────────────────────────────────────────
#  SAVE ALERT TO MONGODB  (for dashboard to read)
# ──────────────────────────────────────────────────────────────
def save_alert_to_db(window_label, direction, missing_buses, window_start, window_end):
    """
    Saves alert to MongoDB dashboard_alerts collection.
    DUPLICATE PREVENTION: checks if same window already alerted today
    before inserting — safe even if schedule_check.py restarts.
    """
    if not is_connected():
        return
    try:
        now   = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")

        # Check if this window already has an alert saved today
        existing = _alerts.find_one({
            "window_label": window_label,
            "date":         today
        })
        if existing:
            print(f"[ALERT] ℹ️  Alert for {window_label} today already in database — skipping duplicate")
            return

        _alerts.insert_one({
            "window_label"  : window_label,
            "direction"     : direction,
            "missing_buses" : missing_buses,
            "missing_count" : len(missing_buses),
            "window_start"  : window_start,
            "window_end"    : window_end,
            "date"          : today,
            "timestamp"     : now.strftime("%Y-%m-%d %H:%M:%S"),
            "datetime"      : now,
            "seen"          : False
        })
        print(f"[ALERT] ✅ Alert saved to MongoDB — {window_label} | {len(missing_buses)} missing")
    except Exception as e:
        print(f"[ALERT] ❌ Failed to save alert: {e}")

# ──────────────────────────────────────────────────────────────
#  PUSH ALERT TO DASHBOARD via backend.py Socket.IO
# ──────────────────────────────────────────────────────────────
def push_alert_to_dashboard(window_label, direction, missing_buses, window_start, window_end):
    """
    Calls backend.py /api/alert/push endpoint which emits
    a Socket.IO event to the dashboard browser.
    Dashboard shows a popup with the missing buses list.
    """
    try:
        payload = {
            "window_label"  : window_label,
            "direction"     : direction,
            "missing_buses" : missing_buses,
            "missing_count" : len(missing_buses),
            "window_start"  : window_start,
            "window_end"    : window_end,
            "timestamp"     : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        resp = requests.post(
            f"{BACKEND_URL}/api/alert/push",
            json=payload,
            timeout=5
        )
        if resp.status_code == 200:
            print(f"[ALERT] ✅ Dashboard alert pushed via backend.py")
        else:
            print(f"[ALERT] ⚠️  Backend returned {resp.status_code}")
    except Exception as e:
        print(f"[ALERT] ⚠️  Could not push to dashboard: {e}")
        print(f"[ALERT]     (Is backend.py running?)")

# ──────────────────────────────────────────────────────────────
#  SEND TELEGRAM ALERT
# ──────────────────────────────────────────────────────────────
def send_telegram_alert(missing_buses, direction, window_start, window_end, window_label):
    now_str    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    bus_list   = "\n".join(f"  • {b}" for b in missing_buses)
    count      = len(missing_buses)

    message = (
        f"🚌 Campus Bus Alert — {window_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date    : {datetime.datetime.now().strftime('%Y-%m-%d')}\n"
        f"⏰ Window  : {window_start} - {window_end}  ({direction})\n"
        f"❌ Missing : {count} bus(es) did not {direction}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Missing buses:\n{bus_list}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"— NCERC Campus Fleet System"
    )

    print(f"\n{'!'*55}")
    print(f"  ALERT — {window_label} {direction} WINDOW CLOSED")
    print(f"  Window   : {window_start} - {window_end}")
    print(f"  Missing  : {count} bus(es)")
    for b in missing_buses:
        print(f"    → {b}")
    print(f"{'!'*55}\n")

    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    sent, failed = 0, 0
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            resp   = requests.post(url, data={
                "chat_id"    : chat_id,
                "text"       : message,
                "parse_mode" : "HTML"
            }, timeout=10)
            result = resp.json()
            if result.get("ok"):
                print(f"[TELEGRAM] ✅ Sent to {chat_id}")
                sent += 1
            else:
                print(f"[TELEGRAM] ❌ Failed {chat_id}: {result.get('description','')}")
                failed += 1
        except Exception as e:
            print(f"[TELEGRAM] ❌ Error {chat_id}: {e}")
            failed += 1
    print(f"[TELEGRAM] Done — {sent} sent, {failed} failed\n")

# ──────────────────────────────────────────────────────────────
#  COMBINED ALERT SENDER
# ──────────────────────────────────────────────────────────────
def send_all_alerts(window_label, direction, missing_buses, window_start, window_end):
    """
    Sends alert via THREE channels simultaneously:
    1. Telegram bot message
    2. MongoDB alerts collection (persistent record)
    3. Dashboard real-time popup via backend.py Socket.IO
    """
    # 1. Telegram
    send_telegram_alert(missing_buses, direction, window_start, window_end, window_label)

    # 2. Save to MongoDB for history
    save_alert_to_db(window_label, direction, missing_buses, window_start, window_end)

    # 3. Push to dashboard popup
    push_alert_to_dashboard(window_label, direction, missing_buses, window_start, window_end)

# ──────────────────────────────────────────────────────────────
#  WINDOW CHECKER
# ──────────────────────────────────────────────────────────────
_alerted_today = set()
_last_date     = None

def reset_daily_tracker():
    global _alerted_today, _last_date
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    today = ist_now.strftime("%Y-%m-%d")
    if _last_date != today:
        _alerted_today = set()
        _last_date     = today
        print(f"[SCHEDULE] New day reset: {today}")

def time_passed(hhmm):
    # use IST timezone (UTC+5:30)
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    t = datetime.datetime.strptime(hhmm, "%H:%M")
    return ist_now >= ist_now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

def check_windows():
    official_buses = load_official_buses()
    if not official_buses:
        print("[SCHEDULE] No buses in bus_numbers.txt")
        return

    # ── MORNING CHECK — runs once after 09:00 ──────────────────
    # Checks MongoDB for ENTRY records between 07:00-09:00 TODAY
    # Works correctly even if you start the program at 20:00
    if "MORNING" not in _alerted_today and time_passed(MORNING_END):
        print(f"\n[SCHEDULE] Checking morning window ({MORNING_START}-{MORNING_END})...")
        detected = get_buses_detected("ENTRY", MORNING_START, MORNING_END)
        missing  = [b for b in official_buses if b not in detected]

        print(f"[SCHEDULE] Official buses : {len(official_buses)}")
        print(f"[SCHEDULE] Entered today  : {len(detected)}")
        print(f"[SCHEDULE] Missing        : {len(missing)}")

        if missing:
            send_all_alerts("MORNING", "ENTRY", missing, MORNING_START, MORNING_END)
        else:
            print(f"[SCHEDULE] ✅ All {len(official_buses)} buses entered on time")

        _alerted_today.add("MORNING")

    # ── EVENING CHECK — runs once after 18:00 ─────────────────
    if "EVENING" not in _alerted_today and time_passed(EVENING_END):
        print(f"\n[SCHEDULE] Checking evening window ({EVENING_START}-{EVENING_END})...")
        detected = get_buses_detected("EXIT", EVENING_START, EVENING_END)
        missing  = [b for b in official_buses if b not in detected]

        print(f"[SCHEDULE] Official buses : {len(official_buses)}")
        print(f"[SCHEDULE] Exited today   : {len(detected)}")
        print(f"[SCHEDULE] Missing        : {len(missing)}")

        if missing:
            send_all_alerts("EVENING", "EXIT", missing, EVENING_START, EVENING_END)
        else:
            print(f"[SCHEDULE] ✅ All {len(official_buses)} buses exited on time")

        _alerted_today.add("EVENING")

# ──────────────────────────────────────────────────────────────
#  MAIN LOOP
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  NCERC Campus Bus Schedule Monitor")
    print(f"  Morning ENTRY window : {MORNING_START} - {MORNING_END}")
    print(f"  Evening EXIT  window : {EVENING_START} - {EVENING_END}")
    print(f"  Check interval       : every {CHECK_INTERVAL_SEC} seconds")
    print(f"  Alerts via           : Telegram + Dashboard popup")
    print("=" * 55)
    print()
    print("  NOTE: Program checks REAL DATA from MongoDB.")
    print("  Start it any time — morning, afternoon, evening.")
    print("  It reads today's records already in the database.")
    print()

    if not connect_db():
        print("[DB] Cannot start — MongoDB not reachable")
        exit(1)

    print("[SCHEDULE] Monitor running. Press Ctrl+C to stop.\n")

    try:
        while True:
            if not is_connected():
                print("[DB] Reconnecting...")
                connect_db()

            reset_daily_tracker()
            check_windows()

            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] Watching... (morning:{('done' if 'MORNING' in _alerted_today else 'pending')}, evening:{('done' if 'EVENING' in _alerted_today else 'pending')})", end="\r")
            time.sleep(CHECK_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\n\n[SCHEDULE] Monitor stopped.")