import subprocess
import sys
import os
import threading

def run_backend():
    os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
    subprocess.run([sys.executable, 'backend.py'])

def run_schedule():
    import time
    time.sleep(10)  # wait for backend to start first
    schedule_path = os.path.join(os.path.dirname(__file__), 'backend', 'schedule_check.py')
    subprocess.run([sys.executable, schedule_path])

threading.Thread(target=run_schedule, daemon=True).start()
run_backend()