"""
run_service.py
Runs the SLT Strategic Initiatives app as a background Windows process.
Same pattern as DemandPulse.

Usage:
  python run_service.py start    → start in background
  python run_service.py stop     → stop background process
  python run_service.py restart  → restart
  python run_service.py status   → check if running

To install as a Windows Service (auto-start on boot):
  pip install pywin32
  python service_install.py install
"""
import subprocess
import sys
import os
import signal
import json
from pathlib import Path

PID_FILE = Path(__file__).parent / ".slt_pid"
LOG_FILE = Path(__file__).parent / "logs" / "slt_app.log"
APP_FILE = Path(__file__).parent / "app.py"

# Read port from .env if available
def get_port():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("APP_PORT="):
                return line.split("=",1)[1].strip()
    return "8502"


def start():
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text())
        try:
            os.kill(pid, 0)
            print(f"✅ SLT app already running (PID {pid})")
            print(f"   Open: http://localhost:{get_port()}")
            return
        except OSError:
            PID_FILE.unlink()

    LOG_FILE.parent.mkdir(exist_ok=True)
    port = get_port()

    # Flask app (was Streamlit). Local dev uses the built-in server; on Azure the
    # platform runs gunicorn against wsgi:app instead.
    cmd = [sys.executable, str(APP_FILE)]

    with open(LOG_FILE, "a") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=log,
                                cwd=str(Path(__file__).parent))

    PID_FILE.write_text(str(proc.pid))
    print(f"🚀 SLT Strategic Initiatives started (PID {proc.pid})")
    print(f"   Open: http://localhost:{port}")
    print(f"   Share on network: http://{{your-ip}}:{port}")
    print(f"   Logs: {LOG_FILE}")


def stop():
    if not PID_FILE.exists():
        print("⚪ SLT app is not running.")
        return
    pid = int(PID_FILE.read_text())
    try:
        if sys.platform == "win32":
            subprocess.call(["taskkill", "/F", "/PID", str(pid)])
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"🛑 SLT app stopped (PID {pid})")
    except Exception as e:
        print(f"Could not stop process: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def status():
    if not PID_FILE.exists():
        print("⚪ SLT app is NOT running.")
        return
    pid = int(PID_FILE.read_text())
    try:
        os.kill(pid, 0)
        print(f"🟢 SLT app is RUNNING (PID {pid})")
        print(f"   Open: http://localhost:{get_port()}")
    except OSError:
        print("🔴 PID file exists but process is not running. Run 'start' to restart.")
        PID_FILE.unlink(missing_ok=True)


def restart():
    stop()
    import time; time.sleep(1)
    start()


if __name__ == "__main__":
    cmds = {"start": start, "stop": stop, "status": status, "restart": restart}
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd in cmds:
        cmds[cmd]()
    else:
        print(f"Usage: python run_service.py [start|stop|restart|status]")
