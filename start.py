import subprocess
import sys
import os

# start backend.py from backend folder
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
subprocess.run([sys.executable, 'backend.py'])