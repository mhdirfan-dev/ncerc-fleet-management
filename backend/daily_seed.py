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
]

DAILY_EXIT_BUSES = [
    {"bus_number": "KL48S1156",  "time": "16:34:24"},
    {"bus_number": "KL45S1156",  "time": "16:42:15"},
    {"bus_number": "KL45A0790",  "time": "16:44:05"},
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