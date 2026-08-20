import http.server
import socketserver
import json
import pathlib
import sys
import threading

# Add Scripts directory to sys.path
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "Scripts"))

try:
    import sync_dashboard_to_sheet as sheet_sync
except ImportError:
    sheet_sync = None

PORT = 8000
DASHBOARD_DIR = pathlib.Path(__file__).parent.parent

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/sync" or self.path == "/api/save":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                pals_data = json.loads(post_data.decode('utf-8'))
                
                # 1. Save to pals.json
                json_path = DASHBOARD_DIR / "pals.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(pals_data, f, indent=2, ensure_ascii=False)
                    
                # 2. Save to pals.js
                js_path = DASHBOARD_DIR / "pals.js"
                with open(js_path, "w", encoding="utf-8") as f:
                    f.write("window.PALS_DATA = ")
                    json.dump(pals_data, f, indent=2, ensure_ascii=False)
                    f.write(";\n")
                    
                print(f"[Dashboard Server] Saved {len(pals_data)} Pals to pals.json and pals.js.")

                # 3. Trigger Google Sheet 'My Pals' sync
                def bg_sheet_sync():
                    try:
                        sheet_sync.sync_dashboard_json_to_sheet()
                    except Exception as err:
                        print(f"[!] Background Sheet sync error: {err}")

                threading.Thread(target=bg_sheet_sync, daemon=True).start()

                response = {
                    "status": "success",
                    "message": f"Successfully saved {len(pals_data)} Pals and started 'My Pals' Google Sheet sync!"
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
                return
        else:
            self.send_response(404)
            self.end_headers()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

import os

def run_server():
    os.chdir(str(DASHBOARD_DIR))
    with ThreadedHTTPServer(("", PORT), DashboardHandler) as httpd:
        print(f"==================================================")
        print(f"   PALBOX DASHBOARD THREADED SERVER RUNNING")
        print(f"   URL: http://localhost:{PORT}")
        print(f"==================================================")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
