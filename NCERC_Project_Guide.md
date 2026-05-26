# NCERC Campus Fleet Management System
## Complete Project Guide: Restructuring + MongoDB Atlas + Deployment Prep

---

## ✅ TASK 1 — Project Understanding Summary

| File | Role |
|------|------|
| `yolo_ocr.py` | AI Engine — reads video, detects buses (YOLOv12), reads plates (EasyOCR), logs Entry/Exit |
| `cont_database.py` | Database Module — all MongoDB connect/save/query functions + offline JSON backup |
| `backend.py` | REST API — Flask server on port 5000, all `/api/...` endpoints + Socket.IO real-time push |
| `schedule_check.py` | Alert Bot — checks morning/evening windows, sends Telegram + dashboard popup alerts |
| `serve_dashboard.py` | Static Server — serves Dashboard.html on port 8080 (needed to avoid CORS errors) |
| `Dashboard.html` | Frontend — live dashboard: entry/exit counts, bus status table, filters, real-time updates |
| `bus_numbers.txt` | Config — 29 registered bus plates; only these buses are saved/alerted |
| `detection_log.json` | Local Backup — every detection is saved here as JSON alongside MongoDB |
| `yolo12n.pt` | AI Model — YOLOv12 Nano, detects bus (COCO class 5) |
| `license_plate_detector.pt` | AI Model — custom YOLO, finds license plate region |

**Data Flow:** Camera video → `yolo_ocr.py` → detects bus → reads plate → validates Kerala format (KL-DD-[A/AA]-NNNN) → crosses virtual tripwire → ENTRY or EXIT → saved to MongoDB + `detection_log.json` → `backend.py` serves data to `Dashboard.html` via REST API + Socket.IO → `schedule_check.py` sends Telegram alerts for missing buses.

---

## ✅ TASK 2 — File Reading: Done

All key files were read and understood. No `yolo12n.pt`, `.pt` model internals, `.mov`/`.avi` videos, `venv/`, or `__pycache__/` were read (as instructed).

---

## ✅ TASK 3 — New Folder Structure for GitHub

**Current problem:** All files are dumped in one flat folder — messy for GitHub.

### New Structure to Create on Your Computer

```
ncerc-fleet-management/
│
├── README.md                          ← (new file you create for GitHub)
├── .gitignore                         ← (new file — tells git what to ignore)
│
├── ai_engine/                         ← All AI / detection code
│   ├── yolo_ocr.py                    ← MOVE from root
│   └── models/                        ← Folder for model files
│       ├── yolo12n.pt                 ← MOVE from root
│       └── license_plate_detector.pt  ← MOVE from root
│
├── backend/                           ← Flask API + database
│   ├── backend.py                     ← MOVE from root
│   ├── cont_database.py               ← MOVE from root
│   └── schedule_check.py              ← MOVE from root
│
├── frontend/                          ← Web interface
│   ├── Dashboard.html                 ← MOVE from root
│   └── serve_dashboard.py             ← MOVE from root
│
├── config/                            ← Configuration files
│   └── bus_numbers.txt                ← MOVE from root
│
└── data/                              ← Runtime data (mostly gitignored)
    └── detection_log.json             ← MOVE from root (will be gitignored)
```

---

### Step-by-Step: How to Reorganize on Your Computer

**Step 1 — Create the new folder structure**

Inside your project folder (wherever you keep the project), create these folders manually:
- `ai_engine/`
- `ai_engine/models/`
- `backend/`
- `frontend/`
- `config/`
- `data/`

**Step 2 — Move files (copy-paste, don't retype)**

| Current location (flat folder) | Move to |
|----------------------------------|---------|
| `yolo_ocr.py` | `ai_engine/yolo_ocr.py` |
| `yolo12n.pt` | `ai_engine/models/yolo12n.pt` |
| `license_plate_detector.pt` | `ai_engine/models/license_plate_detector.pt` |
| `backend.py` | `backend/backend.py` |
| `cont_database.py` | `backend/cont_database.py` |
| `schedule_check.py` | `backend/schedule_check.py` |
| `Dashboard.html` | `frontend/Dashboard.html` |
| `serve_dashboard.py` | `frontend/serve_dashboard.py` |
| `bus_numbers.txt` | `config/bus_numbers.txt` |
| `detection_log.json` | `data/detection_log.json` |

**Step 3 — Update file paths inside the code**

Since you moved files, the path references inside the code need updating. Here is exactly what to change in each file — **only the path strings, no logic changes**:

---

#### `ai_engine/yolo_ocr.py` — change these lines near the top:

```python
# BEFORE:
VIDEO_SOURCE     = "test_video1.mov"
BUS_NUMBERS_FILE = "bus_numbers.txt"
BUS_MODEL        = "yolo12n.pt"
PLATE_MODEL      = "license_plate_detector.pt"
OUTPUT_LOG       = "detection_log.json"
OUTPUT_VIDEO     = "detection_output.avi"

# AFTER:
VIDEO_SOURCE     = "test_video1.mov"               # keep as-is (video stays in root or wherever you run from)
BUS_NUMBERS_FILE = "../config/bus_numbers.txt"
BUS_MODEL        = "models/yolo12n.pt"
PLATE_MODEL      = "models/license_plate_detector.pt"
OUTPUT_LOG       = "../data/detection_log.json"
OUTPUT_VIDEO     = "../data/detection_output.avi"
```

Also update the import at the top of `yolo_ocr.py`:
```python
# BEFORE:
from cont_database import connect, save_detection

# AFTER:
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from cont_database import connect, save_detection
```

---

#### `backend/backend.py` — change this line:

```python
# BEFORE:
BUS_NUMBERS_FILE = "bus_numbers.txt"

# AFTER:
BUS_NUMBERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'bus_numbers.txt')
```

---

#### `backend/cont_database.py` — change this line:

```python
# BEFORE:
BACKUP_FILE = "detection_backup.json"

# AFTER:
BACKUP_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'detection_backup.json')
```

---

#### `backend/schedule_check.py` — change this line:

```python
# BEFORE:
BUS_NUMBERS_FILE = "bus_numbers.txt"

# AFTER:
BUS_NUMBERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'bus_numbers.txt')
```

---

#### `frontend/serve_dashboard.py` — change this line:

```python
# BEFORE:
DASHBOARD_FILE = "Dashboard.html"

# AFTER:
DASHBOARD_FILE = "Dashboard.html"   # no change needed — serve_dashboard.py is in same folder as Dashboard.html
```

---

**Step 4 — Create `.gitignore` file** (create this new file in the root of the project):

```
# Python
venv/
__pycache__/
*.pyc
*.pyo

# Runtime data
data/detection_backup.json
data/detection_output.avi

# Video test files (too large for GitHub)
*.mov
*.MOV
*.avi
*.mp4

# AI model files (too large for GitHub — download separately)
ai_engine/models/yolo12n.pt
ai_engine/models/license_plate_detector.pt

# OS files
.DS_Store
Thumbs.db
```

**Step 5 — How to run after reorganizing**

```
# Terminal 1 — MongoDB
mongod --dbpath C:/data/db

# Terminal 2 — Backend API
cd backend
python backend.py

# Terminal 3 — Dashboard
cd frontend
python serve_dashboard.py

# Terminal 4 — AI Detection
cd ai_engine
python yolo_ocr.py

# Terminal 5 — Alert Monitor (optional)
cd backend
python schedule_check.py
```

---

## ✅ TASK 4 — Switch MongoDB Compass → MongoDB Atlas

**Current situation:** `cont_database.py` and `schedule_check.py` both use `mongodb://localhost:27017/` — this only works when `mongod` is running on your local machine.

**Goal:** Use MongoDB Atlas (cloud) so the database works without running `mongod` locally, and `backend.py` can later be deployed online.

---

### Step 1 — Create Atlas Cluster (free)

1. Go to [https://www.mongodb.com/atlas](https://www.mongodb.com/atlas) → Sign up / Log in
2. Click **"Build a Database"** → Choose **Free (M0 Shared)**
3. Choose a cloud provider (AWS/GCP/Azure) and region closest to you — **Mumbai (ap-south-1)** is best for Kerala
4. Give cluster a name: `ncerc-fleet` → Click **"Create"**

---

### Step 2 — Create a Database User

1. In Atlas sidebar → **Database Access** → **Add New Database User**
2. Username: `ncerc_admin`
3. Password: create a strong password (save it)
4. Role: **"Atlas admin"** or **"Read and write to any database"**
5. Click **"Add User"**

---

### Step 3 — Allow Network Access

1. In Atlas sidebar → **Network Access** → **Add IP Address**
2. For development: click **"Allow Access From Anywhere"** → `0.0.0.0/0`
   - (For production later you will restrict this to your server's IP)
3. Click **"Confirm"**

---

### Step 4 — Get Connection String

1. In Atlas → **Database** → Click **"Connect"** on your cluster
2. Choose **"Connect your application"**
3. Driver: **Python**, Version: **3.6 or later**
4. Copy the connection string — it looks like:
   ```
   mongodb+srv://ncerc_admin:<password>@ncerc-fleet.xxxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
5. Replace `<password>` with your actual password

---

### Step 5 — Update `cont_database.py`

Find this section near the top of `cont_database.py`:

```python
# CURRENT CODE (change this):
MONGO_URI       = "mongodb://localhost:27017/"
# MongoDB Atlas:
# MONGO_URI     = "mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
```

Change it to:
```python
# NEW CODE:
MONGO_URI = "mongodb+srv://ncerc_admin:YOUR_PASSWORD@ncerc-fleet.xxxxxx.mongodb.net/?retryWrites=true&w=majority&appName=ncerc-fleet"
DATABASE_NAME   = "college_bus_system"
COLLECTION_NAME = "bus_detections"
```

Replace `YOUR_PASSWORD` and `ncerc-fleet.xxxxxx` with your actual values.

---

### Step 6 — Update `schedule_check.py`

Find this line near the top of `schedule_check.py`:
```python
# CURRENT CODE:
MONGO_URI = "mongodb://localhost:27017/"
```

Change it to the same Atlas URI:
```python
MONGO_URI = "mongodb+srv://ncerc_admin:YOUR_PASSWORD@ncerc-fleet.xxxxxx.mongodb.net/?retryWrites=true&w=majority"
```

---

### Step 7 — Update `backend.py` (two places)

Find these two functions in `backend.py` that still use `localhost`:

```python
# In get_recent_alerts(), get_today_alerts(), get_alerts_by_date(), unseen_alerts()
# CURRENT CODE (appears 4 times):
client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000)
```

Change all 4 occurrences to:
```python
client = MongoClient("mongodb+srv://ncerc_admin:YOUR_PASSWORD@ncerc-fleet.xxxxxx.mongodb.net/?retryWrites=true&w=majority", serverSelectionTimeoutMS=5000)
```

---

### Step 8 — Test the Atlas Connection

After making the changes, run this to verify:
```bash
cd backend
python cont_database.py
```

Expected output:
```
[DB] ✅ Connected → college_bus_system.bus_detections
[TEST] Inserting test record...
[DB] ✅ Saved: KL08AF3035 | ENTRY | 2026-xx-xx xx:xx:xx
```

Then open MongoDB Compass, paste your Atlas URI in the connection box — you will see the same data in the cloud!

---

### Connect Compass to Atlas (for viewing data)

1. Open MongoDB Compass
2. Click **"New Connection"**
3. Paste your Atlas connection string:
   ```
   mongodb+srv://ncerc_admin:YOUR_PASSWORD@ncerc-fleet.xxxxxx.mongodb.net/
   ```
4. Click **"Connect"**
5. You will see `college_bus_system` database → `bus_detections` collection

From this point, your local Compass shows the same data that the cloud backend writes.

---

## ✅ TASK 5 — Deployment Readiness (What Will Need to Change)

You said: "not currently explain deployment, I ask when finished changes" — so below is just a **brief checklist** of what needs to be changed when you are ready to deploy. No steps yet — just so you know what is coming:

| Component | What will change for deployment |
|-----------|-------------------------------|
| `cont_database.py` | MongoDB URI → already done if you did Task 4 |
| `backend.py` | Move Telegram token + MongoDB URI to environment variables (not hardcoded) |
| `schedule_check.py` | Same — move credentials to env vars |
| `backend.py` | Deploy to cloud server (Render / Railway / EC2) — runs 24/7 |
| `frontend/Dashboard.html` | Change `http://localhost:5000` API calls to your deployed backend URL |
| `serve_dashboard.py` | Not needed in production — Dashboard.html will be hosted on Netlify / Vercel |
| `ai_engine/yolo_ocr.py` | Runs on-site (local machine near gate camera) — no deployment needed |
| `schedule_check.py` | Runs on same server as backend.py |

When you finish the restructuring and Atlas changes and say "ready for deployment", I will walk you through each step.

---

## Summary of What YOU Need to Do Now

1. **Restructure files** — create folders, move files as shown in Task 3 table
2. **Update path strings** — only the path lines listed above (copy-paste exact changes)
3. **Create `.gitignore`** — paste the content above
4. **Create Atlas account** — free, 512MB is more than enough for this project
5. **Replace `MONGO_URI`** in `cont_database.py`, `schedule_check.py`, and `backend.py` (4 spots)
6. **Test** — run `python cont_database.py` to confirm Atlas connection works
7. **Push to GitHub** — `git init`, `git add .`, `git commit -m "initial"`, `git push`

---

*NCERC Campus Fleet Management System — Nehru College of Engineering & Research Centre, Pampady, Thrissur, Kerala*
