"""Windowed launcher for VoiceBridge Studio (the PyInstaller entry point).

A small exe with no ML code in it. It starts the merged backend (TTS, voice
cloning, and speech-to-speech in one FastAPI server that also serves the web
UI) from the project's backend\\venv, opens the browser once the server
answers, and shows a tray icon (Open / View Logs / Quit). The backend runs in
a Windows job object, so it never outlives the launcher.

Build with launcher\\build.bat; the exe must sit in the project root.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "VoiceBridge Studio"
HOST = "127.0.0.1"
PORT = int(os.environ.get("APP_PORT", "17493"))
URL = f"http://{HOST}:{PORT}"
APP_FEATURE = "workspace-voices-v1"
# Process names of the separately installed VoiceBox app and its server sidecar.
STANDALONE_VOICEBOX = {"voicebox.exe", "voicebox-server.exe", "voicebox-server-cuda.exe"}

MB_ICONERROR, MB_ICONWARNING, MB_YESNO, IDYES = 0x10, 0x30, 0x4, 6
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def message(text: str, flags: int = MB_ICONERROR) -> int:
    return ctypes.windll.user32.MessageBoxW(0, text, APP_NAME, flags)


def project_root() -> Path:
    exe_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for candidate in (exe_dir, exe_dir.parent):
        if (candidate / "backend" / "main.py").is_file():
            return candidate
    return exe_dir


def get_json(path: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(URL + path, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def listener_pid() -> int | None:
    output = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW
    ).stdout
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{PORT}"):
            return int(parts[4])
    return None


def process_name(pid: int) -> str:
    output = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
    ).stdout.strip()
    return output.split(",")[0].strip('"').lower() if output.startswith('"') else ""


def stop_standalone_voicebox() -> bool:
    for name in STANDALONE_VOICEBOX:
        subprocess.run(["taskkill", "/IM", name, "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
    for _ in range(50):
        if listener_pid() is None:
            return True
        time.sleep(0.2)
    return False


class KillOnCloseJob:
    """A Windows job object that terminates its processes when the launcher exits."""

    def __init__(self) -> None:
        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wt.HANDLE
        kernel32.OpenProcess.restype = wt.HANDLE
        self._kernel32 = kernel32
        self.handle = kernel32.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))

    def add(self, pid: int) -> None:
        process = self._kernel32.OpenProcess(0x0001 | 0x0100, False, pid)  # TERMINATE | SET_QUOTA
        if process:
            self._kernel32.AssignProcessToJobObject(self.handle, process)
            self._kernel32.CloseHandle(process)


def build_web_ui(root: Path, log) -> bool:
    bun = subprocess.run(["where", "bun"], capture_output=True, text=True, creationflags=NO_WINDOW)
    if bun.returncode != 0:
        return False
    for command in (["bun", "install"], ["bun", "run", "build:web"]):
        if subprocess.run(command, cwd=root, stdout=log, stderr=log, shell=True, creationflags=NO_WINDOW).returncode:
            return False
    return (root / "web" / "dist" / "index.html").is_file()


def tray_icon(root: Path, log_path: Path, on_quit):
    import pystray
    from PIL import Image

    icon_path = root / "tauri" / "src-tauri" / "icons" / "icon.png"
    try:
        image = Image.open(icon_path)
    except OSError:
        image = Image.new("RGB", (32, 32), (56, 189, 248))

    def view_logs(icon, item) -> None:
        os.startfile(str(log_path))  # noqa: S606 - user-initiated, local file

    def quit_app(icon, item) -> None:
        on_quit()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(f"Open {APP_NAME}", lambda icon, item: webbrowser.open(URL), default=True),
        pystray.MenuItem("View Logs", view_logs),
        pystray.MenuItem("Quit", quit_app),
    )
    return pystray.Icon("voicebridge-studio", image, APP_NAME, menu)


def main() -> int:
    root = project_root()
    python = root / "backend" / "venv" / "Scripts" / "python.exe"
    log_path = root / "data" / "logs" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    status = get_json("/sts/status")
    if status and APP_FEATURE in status.get("features", []):
        webbrowser.open(URL)
        return 0

    pid = listener_pid()
    if pid is not None:
        owner = process_name(pid)
        if owner in STANDALONE_VOICEBOX:
            answer = message(
                f"The separately installed VoiceBox app is using port {PORT}.\n\n"
                f"{APP_NAME} includes everything VoiceBox does. Close VoiceBox and continue?",
                MB_ICONWARNING | MB_YESNO,
            )
            if answer != IDYES:
                return 1
            if not stop_standalone_voicebox():
                message("VoiceBox could not be closed. Close it from the tray or Task Manager, then try again.")
                return 1
        else:
            message(f"Port {PORT} is in use by another application ({owner or f'PID {pid}'}).\n\n"
                    "Close it, or set APP_PORT to a different port.")
            return 1

    if not python.is_file():
        message(
            f"The backend environment has not been created yet (expected {python}).\n\n"
            f"In {root}, run:\n\n    just setup-python\n\n"
            "It installs PyTorch and the TTS engines, a multi-gigabyte download."
        )
        return 1
    # Import the app itself, so any missing package is named, not just the core ones.
    probe = subprocess.run(
        [str(python), "-c", "import torch, yt_dlp, backend.app"],
        cwd=root, capture_output=True, text=True, creationflags=NO_WINDOW,
    )
    if probe.returncode != 0:
        missing = next(
            (line.strip() for line in reversed(probe.stderr.splitlines()) if "Error" in line),
            "an import failed",
        )
        message(
            "The backend environment is not finished installing.\n\n"
            f"Missing: {missing}\n\n"
            "If `just setup-python` is still running, wait for it to finish and try again. "
            f"Otherwise run it again in {root}."
        )
        return 1

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== {APP_NAME} starting {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        log.flush()
        if not (root / "web" / "dist" / "index.html").is_file() and not build_web_ui(root, log):
            message("The web UI is not built and could not be built automatically.\n\n"
                    f"Install Bun from https://bun.sh, then run in {root}:\n\n    bun install\n    bun run build:web")
            return 1

        environment = dict(os.environ, PYTHONUNBUFFERED="1", NO_COLOR="1")
        server = subprocess.Popen(
            [str(python), "-m", "backend.main", "--host", HOST, "--port", str(PORT), "--data-dir", str(root / "data")],
            cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW,
        )
    job = KillOnCloseJob()
    job.add(server.pid)

    quitting = threading.Event()

    def stop_server() -> None:
        quitting.set()
        subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)

    icon = tray_icon(root, log_path, stop_server)

    def watch() -> None:
        # The first start loads models lazily, but the server itself answers within seconds to minutes.
        opened = False
        while server.poll() is None:
            if not opened and get_json("/health", timeout=1.0) is not None:
                webbrowser.open(URL)
                opened = True
            time.sleep(0.5)
        if not quitting.is_set():
            message(f"{APP_NAME} stopped unexpectedly (exit code {server.returncode}).\n\nSee {log_path}.")
            icon.stop()

    threading.Thread(target=watch, daemon=True).start()
    icon.run()  # Windows message loop on the main thread; returns after Quit
    if server.poll() is None:
        stop_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
