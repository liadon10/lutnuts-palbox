import http.server
import socketserver
import json
import pathlib
import sys
import threading
import subprocess

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
        # Intercept index.html to inject a cache-busting version on pals.js
        if self.path in ('/', '/index.html'):
            try:
                html_path = DASHBOARD_DIR / "index.html"
                pals_js_path = DASHBOARD_DIR / "pals.js"
                v = int(pals_js_path.stat().st_mtime) if pals_js_path.exists() else 0
                content = html_path.read_text(encoding='utf-8')
                content = content.replace(
                    'src="pals.js"',
                    f'src="pals.js?v={v}"'
                )
                encoded = content.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(encoded)))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(encoded)
                return
            except Exception as e:
                print(f"[!] Error serving index.html: {e}")
        
        # Serve app.js and pals.json without caching so changes are always seen
        if self.path in ('/app.js',) or self.path.startswith('/pals.json'):
            try:
                file_path = DASHBOARD_DIR / self.path.split('?')[0].lstrip('/')
                if file_path.exists():
                    content = file_path.read_bytes()
                    ext = file_path.suffix
                    mime = 'application/javascript' if ext == '.js' else 'application/json'
                    self.send_response(200)
                    self.send_header('Content-type', mime)
                    self.send_header('Content-Length', str(len(content)))
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.end_headers()
                    self.wfile.write(content)
                    return
            except Exception as e:
                print(f"[!] Error serving {self.path}: {e}")
        
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

                # 3. Trigger Google Sheet 'My Pals' sync and Git push
                def bg_sheet_sync():
                    try:
                        sheet_sync.sync_dashboard_json_to_sheet()
                    except Exception as err:
                        print(f"[!] Background Sheet sync error: {err}")
                    
                    try:
                        print("[Dashboard Server] Pushing changes to GitHub Pages...")
                        repo_dir = DASHBOARD_DIR.parent
                        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
                        subprocess.run(["git", "commit", "-m", "Auto-save: Updated Palbox data"], cwd=repo_dir, check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
                        print("[Dashboard Server] Successfully pushed to GitHub!")
                    except subprocess.CalledProcessError as err:
                        # git commit fails if there are no changes, which is fine
                        print(f"[!] Background Git sync info: {err}")

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
        elif self.path in ("/api/run-palworld-sync", "/api/sync-from-save"):
            try:
                base_dir = DASHBOARD_DIR.parent
                sync_script = base_dir / "Scripts" / "palworld_sync.py"
                python_exe = sys.executable
                print(f"[Dashboard Server] Running Palworld Sync script: {sync_script}")

                res = subprocess.run(
                    [python_exe, str(sync_script)],
                    cwd=str(base_dir),
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if res.stdout:
                    print(f"[palworld_sync output]\n{res.stdout}")

                if res.returncode != 0:
                    print(f"[!] palworld_sync error (exit code {res.returncode}):\n{res.stderr}")
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "message": f"Sync process failed (exit code {res.returncode}): {res.stderr[:200] if res.stderr else 'Unknown error'}"
                    }).encode('utf-8'))
                    return

                # Background Git commit & push
                def bg_git_push():
                    try:
                        print("[Dashboard Server] Pushing sync changes to GitHub Pages...")
                        subprocess.run(["git", "add", "."], cwd=base_dir, check=True)
                        subprocess.run(["git", "commit", "-m", "Auto-sync: Updated save data and Palbox"], cwd=base_dir, check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd=base_dir, check=True)
                        print("[Dashboard Server] Successfully pushed to GitHub!")
                    except Exception as err:
                        print(f"[!] Background Git sync info: {err}")

                threading.Thread(target=bg_git_push, daemon=True).start()

                # Get count of updated pals from pals.json
                json_path = DASHBOARD_DIR / "pals.json"
                count = 0
                if json_path.exists():
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            pals_data = json.load(f)
                            count = len(pals_data)
                    except Exception:
                        pass

                response = {
                    "status": "success",
                    "message": f"Successfully scanned save game, updated Google Sheets 'My Pals', and synced {count} Pals to Dashboard!",
                    "count": count
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                print(f"[!] Error during save file sync: {e}")
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
