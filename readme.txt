cd edge
py -3.10 -m venv venv      # if this remove = Remove-Item -Recurse -Force venv

        venv\Scripts\activate
```
                      You should see `(venv)` appear at the start of the line like this:
```
        (venv) PS C:\Users\noufa\Desktop\1\2\edge>

set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
python yolo_ocr.py
Terminal 1:  mongod
Terminal 2:  python backend.py
terminal 3:  python serve_dashboard.py
Terminal 4:  python yolo_ocr.py
Terminal 5:  python schedule_check.py


TELEGRAM_BOT_TOKEN = "8538513607:AAFKk3lUYoQspKmkuGIfH1_-BjiAaE8VXWA"    # e.g. 7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

TELEGRAM_CHAT_IDS = [
    "1908474653",       # Transport Officer  e.g. 123456789   # Principal / Security
]





================================================================================
   NCERC CAMPUS FLEET MANAGEMENT SYSTEM — README
   Nehru College of Engineering & Research Centre, Thrissur, Kerala
================================================================================
   AI-powered bus detection system using YOLOv12 + EasyOCR + MongoDB
   Automatically detects college buses, reads Kerala number plates,
   logs Entry/Exit events, sends alerts, and shows a live dashboard.
================================================================================


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 1 — FILES EXPLANATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────┬────────────────────────────────────────────────┐
│ FILE                        │ PURPOSE                                        │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ yolo_ocr.py                 │ MAIN DETECTION PROGRAM                         │
│                             │ - Reads video from gate camera                 │
│                             │ - Detects buses using YOLOv12 (yolo12n.pt)     │
│                             │ - Detects number plates (license_plate_        │
│                             │   detector.pt)                                 │
│                             │ - Reads plate text using EasyOCR               │
│                             │ - Validates Kerala plate format                │
│                             │   (KL + 2digits + 1-2letters + 4digits)        │
│                             │ - Crosses virtual tripwire → ENTRY or EXIT     │
│                             │ - Saves detection to MongoDB via               │
│                             │   cont_database.py                             │
│                             │ - Shows live OpenCV video window               │
│                             │ - Saves annotated output video                 │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ cont_database.py            │ DATABASE MODULE                                │
│                             │ - Connects to MongoDB                          │
│                             │ - Saves detection records                      │
│                             │ - Provides all query functions used by         │
│                             │   backend.py (get today logs, date range,      │
│                             │   bus status, summary etc.)                    │
│                             │ - Auto backup to detection_backup.json         │
│                             │   if MongoDB is down                           │
│                             │ - Syncs backup to MongoDB on reconnect         │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ backend.py                  │ REST API + REAL-TIME SERVER                    │
│                             │ - Flask web server on port 5000                │
│                             │ - Provides API endpoints for dashboard         │
│                             │ - Socket.IO pushes new detections to           │
│                             │   dashboard instantly (no page refresh)        │
│                             │ - Key endpoints:                               │
│                             │     /api/logs/today                            │
│                             │     /api/logs/week                             │
│                             │     /api/logs/month                            │
│                             │     /api/stats/today                           │
│                             │     /api/summary/today                         │
│                             │     /api/buses                                 │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ schedule_check.py           │ AUTOMATIC ALERT SYSTEM                         │
│                             │ - Runs in background continuously              │
│                             │ - Monitors two daily windows:                  │
│                             │     Morning: 07:00-09:00 (buses should ENTER)  │
│                             │     Evening: 16:00-18:00 (buses should EXIT)   │
│                             │ - After each window closes, checks which       │
│                             │   buses from bus_numbers.txt are missing        │
│                             │ - Sends Telegram message alert listing         │
│                             │   all missing buses                            │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ serve_dashboard.py          │ DASHBOARD WEB SERVER                           │
│                             │ - Simple HTTP server on port 8080              │
│                             │ - Serves dashboard.html to browser             │
│                             │ - Auto-opens browser on start                  │
│                             │ - Required because dashboard.html cannot       │
│                             │   be opened directly as a file (CORS issue)    │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ dashboard.html              │ WEB DASHBOARD INTERFACE                        │
│                             │ - Shows live bus entry/exit counts             │
│                             │ - Shows buses inside/outside campus            │
│                             │ - Full movement log table with search          │
│                             │ - Filter by Today / Week / Month / Custom      │
│                             │ - Filter by Entry or Exit direction            │
│                             │ - Print/export log as statement                │
│                             │ - Real-time updates via Socket.IO              │
│                             │   (new bus detection appears instantly)        │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ bus_numbers.txt             │ OFFICIAL BUS REGISTER                          │
│                             │ - One bus plate per line                       │
│                             │ - Only buses in this list are logged           │
│                             │ - Format: KL08AF3035 (no spaces or dots)       │
│                             │ - Add/remove buses by editing this file        │
│                             │ - Currently has 29 registered buses            │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ detection_log.json          │ LOCAL DETECTION BACKUP LOG                     │
│                             │ - Every detection is saved here locally        │
│                             │ - Also saved to MongoDB simultaneously         │
│                             │ - Fields: bus_number, direction, date,         │
│                             │   time, timestamp, status                      │
│                             │ - Status values: "pending" / "synced"          │
│                             │ - Acts as offline backup if MongoDB is down    │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ yolo12n.pt                  │ BUS DETECTION AI MODEL                         │
│                             │ - YOLOv12 Nano model                           │
│                             │ - Detects buses in video frames                │
│                             │ - COCO class 5 = bus                           │
│                             │ - Tracks bus movement across frames            │
│                             │ - Download:                                    │
│                             │   https://github.com/ultralytics/assets/      │
│                             │   releases/download/v8.3.0/yolo12n.pt         │
├─────────────────────────────┼────────────────────────────────────────────────┤
│ license_plate_detector.pt   │ NUMBER PLATE DETECTION AI MODEL                │
│                             │ - Custom YOLO model for license plates         │
│                             │ - Finds plate region in the frame              │
│                             │ - Crop is passed to EasyOCR for text reading   │
│                             │ - Download:                                    │
│                             │   https://github.com/Muhammad-Zeerak-Khan/    │
│                             │   Automatic-License-Plate-Recognition-        │
│                             │   using-YOLOv8/raw/main/                      │
│                             │   license_plate_detector.pt                   │
└─────────────────────────────┴────────────────────────────────────────────────┘


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 2 — SYSTEM WORKFLOW DIAGRAM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  GATE CAMERA
       │
       │ video frames
       ▼
  ┌─────────────────────────────────────────────────────┐
  │                   yolo_ocr.py                        │
  │                                                      │
  │  Frame → yolo12n.pt ──────► Bus detected?            │
  │                                    │ YES             │
  │  Frame → license_plate_detector.pt ► Plate crop      │
  │                                    │                 │
  │  Plate crop → EasyOCR ────────────► Text read        │
  │                                    │                 │
  │  Kerala format validator ─────────► KL08AF3035 ✓     │
  │                                    │                 │
  │  Bus crosses virtual tripwire ────► ENTRY or EXIT    │
  │                                    │                 │
  │  Match against bus_numbers.txt ───► Official bus? ✓  │
  └─────────────────────────────────────────────────────┘
               │                    │
               │ save               │ save
               ▼                    ▼
  ┌──────────────────┐    ┌───────────────────────┐
  │ detection_log    │    │   cont_database.py     │
  │ .json (local)    │    │         │              │
  └──────────────────┘    │         ▼              │
                          │     MongoDB            │
                          │  college_bus_system    │
                          │  .bus_detections       │
                          └───────────┬────────────┘
                                      │ reads
                                      ▼
                          ┌───────────────────────┐
                          │      backend.py        │
                          │   Flask API :5000      │
                          │   Socket.IO push       │
                          └───────────┬────────────┘
                                      │ HTTP + WebSocket
                                      ▼
                          ┌───────────────────────┐
                          │  serve_dashboard.py    │
                          │   HTTP Server :8080    │
                          │         │              │
                          │         ▼              │
                          │   dashboard.html       │
                          │  (browser interface)   │
                          └───────────────────────┘

  SEPARATELY RUNNING IN BACKGROUND:
  ┌───────────────────────────────────────────────┐
  │             schedule_check.py                  │
  │  Every 60 sec — checks time windows           │
  │  Morning 09:00 → who missed ENTRY? → Telegram │
  │  Evening 18:00 → who missed EXIT?  → Telegram │
  └───────────────────────────────────────────────┘

  DATA FLOW SUMMARY:
  Camera → yolo_ocr.py → cont_database.py → MongoDB
                                          → detection_log.json
                       → backend.py reads MongoDB
                       → dashboard.html shows live data
                       → schedule_check.py alerts missing buses


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 3 — INSTALLATION STEPS (Run in order, first time only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  REQUIREMENTS BEFORE STARTING:
  ─────────────────────────────
  - Python 3.10.11 (MUST be this version — NOT 3.11, 3.12 or 3.13)
    Download: https://www.python.org/downloads/release/python-31011/
  - MongoDB Community Server
    Download: https://www.mongodb.com/try/download/community
  - Git (optional but recommended)
    Download: https://git-scm.com/download/win

  ────────────────────────────────────────────────────────────────
  STEP 1 — Create virtual environment
  ────────────────────────────────────────────────────────────────
  Open PowerShell inside the edge folder:

    cd C:\Users\noufa\Desktop\1\2\edge
    py -3.10 -m venv venv

  NOTE: Use "py -3.10" not "python" to ensure Python 3.10 is used.

  ────────────────────────────────────────────────────────────────
  STEP 2 — Activate virtual environment
  ────────────────────────────────────────────────────────────────

    .\venv\Scripts\Activate.ps1

  You will see (venv) appear at the start of your terminal line.
  You must activate venv EVERY TIME you open a new terminal.

  If activation is blocked by policy, run this once:
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

  ────────────────────────────────────────────────────────────────
  STEP 3 — Install packages IN THIS EXACT ORDER
  ────────────────────────────────────────────────────────────────

    pip install numpy==1.26.4

    pip install Pillow==10.4.0

    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

    pip install paddlepaddle

    pip install easyocr --no-deps

    pip install opencv-python==4.8.1.78

    pip install ultralytics==8.4.21

    pip install pymongo

    pip install flask flask-cors flask-socketio

    pip install requests

  IMPORTANT NOTES:
  - Install numpy FIRST before everything else
  - Use "easyocr --no-deps" to prevent it from overwriting opencv
  - Do NOT run "pip install easyocr" without --no-deps
  - Do NOT install opencv-python-headless (no GUI support)

  ────────────────────────────────────────────────────────────────
  STEP 4 — Download AI model files
  ────────────────────────────────────────────────────────────────

  Open browser and download these two files into the edge folder:

  yolo12n.pt:
    https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo12n.pt

  license_plate_detector.pt:
    https://github.com/Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8/raw/main/license_plate_detector.pt

  ────────────────────────────────────────────────────────────────
  STEP 5 — Set environment variable (every new terminal)
  ────────────────────────────────────────────────────────────────

    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True"

  ────────────────────────────────────────────────────────────────
  STEP 6 — Verify installation
  ────────────────────────────────────────────────────────────────

    python -c "import cv2; print('OpenCV:', cv2.__version__)"
    python -c "import numpy; print('NumPy:', numpy.__version__)"
    python -c "import easyocr; print('EasyOCR: OK')"
    python -c "from ultralytics import YOLO; print('Ultralytics: OK')"
    python -c "from pymongo import MongoClient; print('PyMongo: OK')"
    python -c "import flask; print('Flask: OK')"

  Expected output:
    OpenCV: 4.8.1.78
    NumPy: 1.26.4
    EasyOCR: OK
    Ultralytics: OK
    PyMongo: OK
    Flask: OK


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 4 — HOW TO RUN THE SYSTEM (Every day)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Open 4 separate PowerShell terminals.
  In EVERY terminal, first navigate to edge folder and activate venv:

    cd C:\Users\noufa\Desktop\1\2\edge
    .\venv\Scripts\Activate.ps1
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True"

  ════════════════════════════════════════════
  TERMINAL 1 — Start MongoDB (database)
  ════════════════════════════════════════════
    mongod --dbpath C:/data/db

  Keep this running. Do not close.
  If C:/data/db does not exist, create it first:
    mkdir C:/data/db

  ════════════════════════════════════════════
  TERMINAL 2 — Start Backend API
  ════════════════════════════════════════════
    cd C:\Users\noufa\Desktop\1\2\edge
    .\venv\Scripts\Activate.ps1
    python backend.py

  Wait until you see:
    [DB] Connected to MongoDB
    [API] Starting Flask server...

  ════════════════════════════════════════════
  TERMINAL 3 — Start Dashboard
  ════════════════════════════════════════════
    cd C:\Users\noufa\Desktop\1\2\edge
    .\venv\Scripts\Activate.ps1
    python serve_dashboard.py

  Browser opens automatically at http://localhost:8080/dashboard.html
  If it does not open, open browser manually and go to that address.

  ════════════════════════════════════════════
  TERMINAL 4 — Start Detection (main program)
  ════════════════════════════════════════════
    cd C:\Users\noufa\Desktop\1\2\edge
    .\venv\Scripts\Activate.ps1
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True"
    python yolo_ocr.py

  A video window opens showing live detection.
  Press Q to stop detection.

  ════════════════════════════════════════════
  TERMINAL 5 — Start Alert Monitor (optional)
  ════════════════════════════════════════════
    cd C:\Users\noufa\Desktop\1\2\edge
    .\venv\Scripts\Activate.ps1
    python schedule_check.py

  Runs in background checking morning/evening windows.
  Sends Telegram alert if buses are missing.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 5 — VENV TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  If you face any of these problems:
  - "ModuleNotFoundError" for any package
  - numpy version conflict errors
  - opencv imshow crash
  - Package version mismatch after pip install

  SOLUTION — Delete venv and reinstall from scratch:

  ────────────────────────────────────────────
  Step A — Deactivate and delete old venv
  ────────────────────────────────────────────
    deactivate
    Remove-Item -Recurse -Force .\venv

  ────────────────────────────────────────────
  Step B — Create fresh venv
  ────────────────────────────────────────────
    py -3.10 -m venv venv
    .\venv\Scripts\Activate.ps1

  ────────────────────────────────────────────
  Step C — Reinstall all packages in order
  ────────────────────────────────────────────
    pip install numpy==1.26.4
    pip install Pillow==10.4.0
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip install paddlepaddle
    pip install easyocr --no-deps
    pip install opencv-python==4.8.1.78
    pip install ultralytics==8.4.21
    pip install pymongo
    pip install flask flask-cors flask-socketio
    pip install requests

  ────────────────────────────────────────────
  Step D — Verify before running
  ────────────────────────────────────────────
    python -c "import cv2; print(cv2.__version__)"
    → Must show 4.8.1.78

    python -c "import numpy; print(numpy.__version__)"
    → Must show 1.26.4

  ────────────────────────────────────────────
  Common error messages and fixes:
  ────────────────────────────────────────────

  ERROR: "The function is not implemented" on cv2.imshow
  FIX:   pip uninstall opencv-python opencv-python-headless -y
         pip install opencv-python==4.8.1.78

  ERROR: "_ARRAY_API not found" or "numpy.core.multiarray failed"
  FIX:   pip uninstall numpy -y
         pip install numpy==1.26.4
         pip uninstall opencv-python -y
         pip install opencv-python==4.8.1.78

  ERROR: "ConvertPirAttribute2RuntimeAttribute" (PaddleOCR)
  FIX:   This is a PaddleOCR bug on Windows. System uses EasyOCR.
         Do not use PaddleOCR. easyocr is already installed.

  ERROR: "ModuleNotFoundError: No module named 'flask_socketio'"
  FIX:   pip install flask-socketio

  ERROR: "ServerSelectionTimeoutError" (MongoDB)
  FIX:   MongoDB is not running. Start it first:
         mongod --dbpath C:/data/db

  ERROR: "FileNotFoundError: yolo12n.pt"
  FIX:   Download model file from browser:
         https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo12n.pt
         Place in edge folder.

  ERROR: Script not loading in PowerShell (execution policy)
  FIX:   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 6 — FOLDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  C:\Users\noufa\Desktop\1\2\edge\
  │
  ├── yolo_ocr.py                 ← Main detection program
  ├── cont_database.py            ← MongoDB database module
  ├── backend.py                  ← Flask API server
  ├── schedule_check.py           ← Telegram alert monitor
  ├── serve_dashboard.py          ← Dashboard web server
  ├── dashboard.html              ← Web dashboard interface
  │
  ├── bus_numbers.txt             ← Registered bus plate numbers
  ├── detection_log.json          ← Local detection backup log
  │
  ├── yolo12n.pt                  ← Bus detection AI model
  ├── license_plate_detector.pt   ← Plate detection AI model
  │
  ├── detection_output.avi        ← Saved annotated video (generated)
  ├── detection_backup.json       ← Auto-created if MongoDB is down
  │
  └── venv\                       ← Python virtual environment
       └── (all installed packages)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 7 — KERALA NUMBER PLATE FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Format:   KL - DD - [A or AA] - NNNN
  Example:  KL   08    AF         3035

  KL   = Kerala state code (always)
  DD   = District number (01 to 75)
  A/AA = 1 or 2 alphabet series letters
  NNNN = 4 digit vehicle number

  The system automatically:
  - Validates this format for every OCR reading
  - Corrects common OCR errors (O vs 0, I vs 1, S vs 5 etc.)
  - Accepts 1 character difference for fuzzy matching
  - Combines two-row plate fragments (e.g. "KL48" + "T0617")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SYSTEM: NCERC Campus Fleet Management
  Built with: Python 3.10, YOLOv12, EasyOCR, MongoDB, Flask, Socket.IO
  College: Nehru College of Engineering & Research Centre
           Pampady, Thrissur, Kerala — 680597
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━