# ============================================================
#  FILE: edge/serve_dashboard.py
#  PURPOSE: Serve dashboard.html on http://localhost:8080
#  Run:     python serve_dashboard.py
#  Then open browser: http://localhost:8080
# ============================================================

import http.server
import socketserver
import webbrowser
import os
import threading

PORT = 8080
DASHBOARD_FILE = "Dashboard.html" # no change needed — serve_dashboard.py is in same folder as Dashboard.html

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress request logs

def open_browser():
    import time
    time.sleep(1)
    webbrowser.open(f"http://localhost:{PORT}/{DASHBOARD_FILE}")
    print(f"[DASHBOARD] Opened in browser: http://localhost:{PORT}/{DASHBOARD_FILE}")

if __name__ == "__main__":
    if not os.path.exists(DASHBOARD_FILE):
        print(f"[ERROR] {DASHBOARD_FILE} not found in edge folder!")
        exit(1)

    print("="*55)
    print("  Campus Fleet Dashboard Server")
    print("="*55)
    print(f"[DASHBOARD] Serving on http://localhost:{PORT}")
    print(f"[DASHBOARD] Opening browser automatically...")
    print(f"[DASHBOARD] Press Ctrl+C to stop\n")

    threading.Thread(target=open_browser, daemon=True).start()

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[DASHBOARD] Server stopped.")