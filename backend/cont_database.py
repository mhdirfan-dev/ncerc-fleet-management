# ============================================================
#  FILE: edge/cont_database.py
#  PURPOSE: MongoDB connection + all query functions
#  DATABASE: college_bus_system
#  COLLECTION: bus_detections
# ============================================================

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import datetime
import json
import os

# ──────────────────────────────────────────────────────────────
# CONFIGURATION — change MONGO_URI to your connection string
# ──────────────────────────────────────────────────────────────
MONGO_URI       = "mongodb+srv://ncerc_admin:ncerc123@ncerc-fleet.utptozm.mongodb.net/?appName=ncerc-fleet"
# MongoDB Atlas:
# MONGO_URI     = "mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"

DATABASE_NAME   = "college_bus_system"
COLLECTION_NAME = "bus_detections"
BACKUP_FILE     = "os.path.join(os.path.dirname(__file__), '..', 'data', 'detection_backup.json')"

_client     = None
_db         = None
_collection = None

# ──────────────────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────────────────
def connect():
    global _client, _db, _collection
    try:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command('ping')
        _db         = _client[DATABASE_NAME]
        _collection = _db[COLLECTION_NAME]
        _collection.create_index("bus_number")
        _collection.create_index("timestamp")
        _collection.create_index("direction")
        _collection.create_index("date")
        _collection.create_index("status")
        print(f"[DB] ✅ Connected → {DATABASE_NAME}.{COLLECTION_NAME}")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"[DB] ❌ Connection failed: {e}")
        return False

def disconnect():
    global _client
    if _client:
        _client.close()
        print("[DB] Disconnected")

def is_connected():
    global _client
    try:
        if _client:
            _client.admin.command('ping')
            return True
    except Exception:
        pass
    return False

# ──────────────────────────────────────────────────────────────
# SAVE DETECTION
# ──────────────────────────────────────────────────────────────
def save_detection(bus_number, direction, timestamp=None):
    global _collection
    if not is_connected():
        if not connect():
            _save_backup(bus_number, direction, timestamp)
            return None

    if timestamp is None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    document = {
        "bus_number" : bus_number,
        "direction"  : direction,
        "date"       : dt.strftime("%Y-%m-%d"),
        "time"       : dt.strftime("%H:%M:%S"),
        "timestamp"  : timestamp,
        "datetime"   : dt,
        "status"     : "synced",
        "created_at" : datetime.datetime.now()
    }
    try:
        result = _collection.insert_one(document)
        print(f"[DB] ✅ Saved: {bus_number} | {direction} | {timestamp}")
        return result.inserted_id
    except Exception as e:
        print(f"[DB] ❌ Save failed: {e}")
        _save_backup(bus_number, direction, timestamp)
        return None

# ──────────────────────────────────────────────────────────────
# BACKUP
# ──────────────────────────────────────────────────────────────
def _save_backup(bus_number, direction, timestamp):
    if timestamp is None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"bus_number": bus_number, "direction": direction,
             "timestamp": timestamp, "status": "pending_sync"}
    backup = []
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "r") as f:
            try: backup = json.load(f)
            except: backup = []
    backup.append(entry)
    with open(BACKUP_FILE, "w") as f:
        json.dump(backup, f, indent=2)
    print(f"[DB] ⚠️  Backup saved: {BACKUP_FILE}")

def sync_backup():
    if not os.path.exists(BACKUP_FILE) or not is_connected():
        return
    with open(BACKUP_FILE, "r") as f:
        try: entries = json.load(f)
        except: return
    if not entries:
        return
    print(f"[DB] Syncing {len(entries)} backup entries...")
    success = 0
    for e in entries:
        if save_detection(e["bus_number"], e["direction"], e["timestamp"]):
            success += 1
    if success == len(entries):
        os.remove(BACKUP_FILE)
        print(f"[DB] ✅ All {success} entries synced")
    else:
        print(f"[DB] ⚠️  Synced {success}/{len(entries)}")

# ──────────────────────────────────────────────────────────────
# QUERY FUNCTIONS
# ──────────────────────────────────────────────────────────────
def get_today_logs():
    global _collection
    if not is_connected(): return []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return list(_collection.find({"date": today}, {"_id": 0})
                .sort("datetime", -1))

def get_logs_by_bus(bus_number):
    global _collection
    if not is_connected(): return []
    return list(_collection.find({"bus_number": bus_number}, {"_id": 0})
                .sort("datetime", -1))

def get_logs_by_date(date_str):
    global _collection
    if not is_connected(): return []
    return list(_collection.find({"date": date_str}, {"_id": 0})
                .sort("datetime", 1))

def get_logs_by_date_range(start_date, end_date):
    """
    Get all logs between start_date and end_date inclusive.
    Both params: 'YYYY-MM-DD' strings.
    Used by /api/logs/week, /api/logs/month, /api/logs/range
    """
    global _collection
    if not is_connected(): return []
    return list(_collection.find(
        {"date": {"$gte": start_date, "$lte": end_date}},
        {"_id": 0}
    ).sort("datetime", -1))

def get_last_n_logs(n=20):
    global _collection
    if not is_connected(): return []
    return list(_collection.find({}, {"_id": 0})
                .sort("datetime", -1).limit(n))

def get_bus_status(bus_number):
    global _collection
    if not is_connected(): return None
    last = _collection.find_one(
        {"bus_number": bus_number}, {"_id": 0},
        sort=[("datetime", -1)]
    )
    return last["direction"] if last else None

def get_all_buses_today():
    global _collection
    if not is_connected(): return []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": today}},
        {"$sort":  {"datetime": -1}},
        {"$group": {
            "_id":            "$bus_number",
            "last_direction": {"$first": "$direction"},
            "last_seen":      {"$first": "$timestamp"},
            "total_events":   {"$sum": 1}
        }},
        {"$sort": {"last_seen": -1}}
    ]
    return list(_collection.aggregate(pipeline))

def update_status(bus_number, timestamp, new_status):
    global _collection
    if not is_connected(): return False
    r = _collection.update_one(
        {"bus_number": bus_number, "timestamp": timestamp},
        {"$set": {"status": new_status}}
    )
    return r.modified_count > 0
def clear_old_records(days_to_keep=365):
    global _collection
    if not is_connected():
        return
    cutoff_date = (datetime.datetime.now() - 
                   datetime.timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
    result = _collection.delete_many({"date": {"$lt": cutoff_date}})
    print(f"[DB] Cleared {result.deleted_count} records older than {cutoff_date}")
# ──────────────────────────────────────────────────────────────
# TEST
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*50)
    print(" MongoDB Connection Test")
    print("="*50)
    if connect():
        print("\n[TEST] Inserting test record...")
        save_detection("KL08AF3035", "ENTRY",
                       datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("\n[TEST] Today's logs:")
        for log in get_today_logs():
            print(f"  {log['bus_number']} | {log['direction']} | {log['timestamp']}")
        print("\n[TEST] Bus summary today:")
        for bus in get_all_buses_today():
            print(f"  {bus['_id']} | {bus['last_direction']} | events={bus['total_events']}")
        disconnect()
    else:
        print("\n❌ MongoDB not reachable")
        print("   Start MongoDB:  mongod --dbpath C:/data/db")