import subprocess
import sys
import os
import threading

def run_backend():
    os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
    subprocess.run([sys.executable, 'backend.py'])

def run_schedule():
    import time
    time.sleep(10)
    schedule_path = os.path.join(os.path.dirname(__file__), 'backend', 'schedule_check.py')
    subprocess.run([sys.executable, schedule_path])

backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

# start schedule checker
threading.Thread(target=run_schedule, daemon=True).start()

# start daily seed
from daily_seed import start_daily_seed
start_daily_seed()

subprocess.run([sys.executable, 'backend.py'])