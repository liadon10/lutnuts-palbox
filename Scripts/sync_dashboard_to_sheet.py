import pathlib
import json
import subprocess
import sys

def sync_dashboard_json_to_sheet():
    """Reads Dashboard/pals.json and triggers Google Sheet synchronization."""
    script_dir = pathlib.Path(__file__).parent
    sync_script = script_dir / "palworld_sync.py"
    if sync_script.is_file():
        try:
            print("[Sync] Running palworld_sync.py in background...")
            subprocess.run([sys.executable, str(sync_script)], check=False)
        except Exception as e:
            print(f"[!] Error triggering palworld_sync.py: {e}")
    else:
        print("[!] palworld_sync.py script not found in Scripts directory.")

if __name__ == "__main__":
    sync_dashboard_json_to_sheet()
