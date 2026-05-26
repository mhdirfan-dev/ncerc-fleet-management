# ============================================================
#  FILE: backend/daily_seed.py
#  PURPOSE: Saves fixed bus detection records every day
#           automatically with today's date and correct times
#           Runs at startup and then every 24 hours
# ============================================================

import datetime
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from cont_database import save_detection, is_connected, connect

# ── Fixed bus detections to save every day ──────────────────
# These are the exact buses from your detection_log.json
# Edit this list to add or remove buses anytime

DAILY_ENTRY_BUSES = [
    {"bus_number": "KL13Q1577",  "time": "07:34:24"},
    {"bus_number": "KL48T0617",  "time": "07:35:40"},
    {"bus_number": "KL08Z0277",  "time": "07:36:49"},
    {"bus_number": "KL08AF3035", "time": "07:38:10"},
    {"bus_number": "KL48S1156",  "time": "07:40:22"},
    {"bus_number": "KL45S1156",  "time": "07:42:15"},
    {"bus_number": "KL45A0790",  "time": "07:44:05"},
    {"bus_number": "KL48U9410",  "time": "07:46:30"},
    {"bus_number": "KL08AH8299", "time": "07:48:00"},
    {"bus_number": "KL51R2595",  "time": "07:50:12"},
    {"bus_number": "KL51P0395",  "time": "07:52:44"},
    {"bus_number": "KL51Q6598",  "time": "07:54:18"},
    {"bus_number": "KL51R2831",  "time": "07:56:33"},
    {"bus_number": "KL13S7247",  "time": "07:58:45"},
    {"bus_number": "KL08AK6111", "time": "08:00:10"},
    {"bus_number": "KL41A5646",  "time": "08:02:22"},
    {"bus_number": "KL51P0309",  "time": "08:04:35"},
    {"bus_number": "KL48U9432",  "time": "08:06:48"},
    {"bus_number": "KL48C7262",  "time": "08:08:15"},
    {"bus_number": "KL51P8133",  "time": "08:10:30"},
    {"bus_number": "KL51P8120",  "time": "08:12:44"},
    {"bus_number": "KL02T8058",  "time": "08:14:55"},
    {"bus_number": "KL51Q6690",  "time": "08:16:10"},
    {"bus_number": "KL51Q6612",  "time": "08:18:22"},
    {"bus_number": "KL48S1103",  "time": "08:20:35"},
    {"bus_number": "KL51Q6646",  "time": "08:22:48"},
    {"bus_number": "KL48T0609",  "time": "08:24:15"},
    {"bus_number": "KL51D8105",  "time": "08:26:30"},
]

DAILY_EXIT_BUSES = [
    {"bus_number": "KL13Q1577",  "time": "16:34:24"},
    {"bus_number": "KL48T0617",  "time": "16:35:40"},
    {"bus_number": "KL08Z0277",  "time": "16:36:49"},
    {"bus_number": "KL08AF3035", "time": "16:38:10"},
    {"bus_number": "KL48S1156",  "time": "16:40:22"},
    {"bus_number": "KL45S1156",  "time": "16:42:15"},
    {"bus_number": "KL45A0790",  "time": "16:44:05"},
    {"bus_number": "KL48U9410",  "time": "16:46:30"},
    {"bus_number": "KL08AH8299", "time": "16:48:00"},
    {"bus_number": "KL51R2595",  "time": "16:50:12"},
    {"bus_number": "KL51P0395",  "time": "16:52:44"},
    {"bus_number": "KL51Q6598",  "time": "16:54:18"},
    {"bus_number": "KL51R2831",  "time": "16:56:33"},
    {"bus_number": "KL13S7247",  "time": "16:58:45"},
    {"bus_number": "KL08AK6111", "time": "17:00:10"},
    {"bus_number": "KL41A5646",  "time": "17:02:22"},
    {"bus_number": "KL51P0309",  "time": "17:04:35"},
    {"bus_number": "KL48U9432",  "time": "17:06:48"},
    {"bus_number": "KL48C7262",  "time": "17:08:15"},
    {"bus_number": "KL51P8133",  "time": "17:10:30"},
    {"bus_number": "KL51P8120",  "time": "17:12:44"},
    {"bus_number": "KL02T8058",  "time": "17:14:55"},
    {"bus_number": "KL51Q6690",  "time": "17:16:10"},
    {"bus_number": "KL51Q6612",  "time": "17:18:22"},
    {"bus_number": "KL48S1103",  "time": "17:20:35"},
    {"bus_number": "KL51Q6646",  "time": "17:22:48"},
    {"bus_number": "KL48T0609",  "time": "17:24:15"},
    {"bus_number": "KL51D8105",  "time": "17:26:30"},
]

# ── Check if already seeded today ───────────────────────────
def already_seeded_today():
    from cont_database import get_today_logs
    logs = get_today_logs()
    return len(logs) > 0

# ── Save one day of records ──────────────────────────────────
def seed_today():
    if not is_connected():
        connect()
    if already_seeded_today():
        print("[SEED] Already seeded today — skipping")
        return

    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    today   = ist_now.strftime("%Y-%m-%d")

    print(f"[SEED] Seeding {len(DAILY_ENTRY_BUSES)} entry records for {today}")
    for bus in DAILY_ENTRY_BUSES:
        timestamp = f"{today} {bus['time']}"
        save_detection(bus["bus_number"], "ENTRY", timestamp)

    print(f"[SEED] Seeding {len(DAILY_EXIT_BUSES)} exit records for {today}")
    for bus in DAILY_EXIT_BUSES:
        timestamp = f"{today} {bus['time']}"
        save_detection(bus["bus_number"], "EXIT", timestamp)

    print(f"[SEED] Done — {len(DAILY_ENTRY_BUSES) + len(DAILY_EXIT_BUSES)} records saved")

# ── Run daily at midnight IST ────────────────────────────────
def run_daily_seed():
    while True:
        seed_today()
        # wait until next midnight IST
        utc_now  = datetime.datetime.utcnow()
        ist_now  = utc_now + datetime.timedelta(hours=5, minutes=30)
        tomorrow = (ist_now + datetime.timedelta(days=1)).replace(
                    hour=0, minute=1, second=0, microsecond=0)
        wait_seconds = (tomorrow - ist_now).total_seconds()
        print(f"[SEED] Next seed in {int(wait_seconds/3600)} hours")
        time.sleep(wait_seconds)

def start_daily_seed():
    threading.Thread(target=run_daily_seed, daemon=True).start()
    print("[SEED] Daily seed scheduler started")