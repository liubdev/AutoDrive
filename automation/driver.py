"""
UI driver - wraps pywinauto for process/window management
"""
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional

import psutil
from pywinauto import Application
from pywinauto.findwindows import find_elements
from pywinauto.timings import Timings

from config import settings

logger = logging.getLogger("autocar.driver")


class AppDriver:
    """Application driver - manages process lifecycle and top-level windows"""

    def __init__(self):
        self._app: Optional[Application] = None
        self._process: Optional[psutil.Process] = None
        self._executable: Optional[str] = None
        Timings.Fast()

    # -- Launch / Connect -------------------------------------------

    def start(self, path: str, args: str = "", timeout: int = None) -> "AppDriver":
        """
        Launch an EXE and connect to it

        Uses subprocess.Popen to avoid pywinauto's WaitForInputIdle hang.

        Window matching strategy (strict priority):
          1. PID match — window whose process_id equals the subprocess PID
          2. Exe-in-class match — executable name appears in window class_name
             (e.g. "Fork" → class="Window") — NO title matching to avoid
             false positives with terminal tabs

        Args:
            path: EXE path (e.g. notepad.exe or C:\\full\\path\\app.exe)
            args: command-line arguments
            timeout: seconds to wait for the window to appear
        """
        self._executable = path
        timeout = timeout or settings.default_timeout

        logger.info(f"Starting: {path} {args}")

        # Launch directly (no shell=True to avoid intermediate cmd.exe)
        cmd_parts = [path]
        if args:
            cmd_parts.extend(args.split())
        proc = subprocess.Popen(cmd_parts)

        exe_name = Path(path).stem.lower()

        deadline = time.time() + timeout
        matched_window = None

        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"Process exited immediately (code={proc.returncode})"
                )

            try:
                wins = find_elements(backend=settings.uia_backend,
                                     top_level_only=True)

                # Strategy 1: match by PID (MOST reliable)
                matched = [w for w in wins if w.process_id == proc.pid]

                # Strategy 2: match by executable name in CLASS_NAME only
                #   (NEVER match by title — title substring matching is
                #    too prone to false positives with terminal/PowerShell tabs.
                #    e.g. "fork" should NOT match "Windows控件自动化fork实现")
                if not matched:
                    matched = [
                        w for w in wins
                        if (w.class_name and exe_name.lower() in w.class_name.lower())
                    ]

                if matched:
                    matched_window = matched[0]
                    break
            except Exception:
                pass

            time.sleep(0.3)

        if matched_window is None:
            raise RuntimeError(
                f"Process started but no window detected (PID={proc.pid}, timeout={timeout}s)"
            )

        # Connect via window handle
        self._app = Application(backend=settings.uia_backend)
        self._app.connect(handle=matched_window.handle)
        actual_pid = matched_window.process_id
        self._process = psutil.Process(actual_pid)
        logger.info(f"Process started, PID={actual_pid}")
        return self

    def connect(self, path: str = None, pid: int = None,
                handle: int = None, title: str = None) -> "AppDriver":
        """
        Connect to an already running process

        Connect by one of: path, pid, handle, or window title.
        """
        self._app = Application(backend=settings.uia_backend)

        if pid:
            self._app.connect(process=pid)
            conn_by = f"pid={pid}"
        elif handle:
            self._app.connect(handle=handle)
            conn_by = f"handle={handle}"
        elif path:
            self._app.connect(path=path)
            conn_by = f"path={path}"
        elif title:
            wins = find_elements(backend=settings.uia_backend, top_level_only=True)
            matched = None
            for w in wins:
                if title.lower() in (w.name or "").lower():
                    matched = w
                    break
            if matched is None:
                raise LookupError(f"No window found with title containing '{title}'")
            self._app.connect(handle=matched.handle)
            conn_by = f"title='{title}'"
        else:
            raise ValueError("Must provide one of: path, pid, handle, title")

        self._process = psutil.Process(self._app.process)
        self._executable = self._process.exe()
        logger.info(f"Connected ({conn_by}), PID={self._app.process}")
        return self

    def connect_existing(self, path: str) -> "AppDriver":
        """Connect to a running process by its executable path"""
        for proc in psutil.process_iter(["pid", "exe", "name"]):
            try:
                if proc.info["exe"] and Path(proc.info["exe"]).resolve() == Path(path).resolve():
                    return self.connect(pid=proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        raise LookupError(f"No running process found for: {path}")

    def connect_by_pid(self, pid: int) -> "AppDriver":
        """Connect by PID (most reliable)"""
        return self.connect(pid=pid)

    # -- Window operations -----------------------------------------

    @property
    def top_window(self):
        """Get the current top-level window"""
        if not self._app:
            raise RuntimeError("Call start() or connect() first")
        return self._app.top_window()

    def wait_window(self, title: str, timeout: int = None):
        """Wait for a window with matching title to appear"""
        timeout = timeout or settings.default_timeout
        logger.info(f"Waiting for window: '{title}' (timeout={timeout}s)")
        return self._app.window(title=title).wait("visible", timeout=timeout)

    def window(self, **criteria):
        """
        Get a window by criteria

        Examples:
            driver.window(title="Calculator")
            driver.window(class_name="CalcFrame")
        """
        return self._app.window(**criteria)

    def list_windows(self):
        """List all top-level windows"""
        wins = find_elements(backend=settings.uia_backend, top_level_only=True)
        result = []
        for w in wins:
            try:
                rect = w.rectangle
                result.append({
                    "handle": w.handle,
                    "title": w.name or "",
                    "class": w.class_name or "",
                    "visible": w.visible,
                    "pid": w.process_id,
                    "rect": (rect.left, rect.top, rect.right, rect.bottom),
                })
            except Exception:
                continue
        return result

    # -- Process management ----------------------------------------

    @property
    def is_running(self) -> bool:
        """Check if the process is still running"""
        if self._process:
            return self._process.is_running()
        return False

    @property
    def pid(self) -> Optional[int]:
        """Get the process PID"""
        if self._process:
            return self._process.pid
        if self._app:
            try:
                return self._app.process
            except Exception:
                pass
        return None

    def kill(self):
        """Force-kill the process"""
        if self._process:
            logger.warning(f"Killing process PID={self._process.pid}")
            self._process.kill()
            self._process = None
            self._app = None

    def disconnect(self):
        """
        Disconnect from the process WITHOUT killing it.

        Use this for apps like Fork/Chrome that should keep running.
        """
        if self._app:
            logger.info("Disconnected from process (process left running)")
            self._app = None
            self._process = None

    def close(self):
        """
        Safely close the application

        Note: Some apps (Fork, Chrome, etc.) should use disconnect()
        instead to avoid killing them.
        """
        if self._app:
            try:
                self._app.kill()
                logger.info("Process closed")
            except Exception:
                pass
            self._app = None
            self._process = None

    def restart(self):
        """Restart the application"""
        exe = self._executable
        self.close()
        if exe:
            self.start(exe)

    # -- Menu operations -------------------------------------------

    def menu_select(self, path: str):
        """
        Select a menu item by path (format: "Menu->Submenu->Command")

        Example:
            driver.menu_select("File->Open")
        """
        window = self.top_window
        items = [item.strip() for item in path.split("->")]
        current = window
        for item in items:
            current = current.child_window(title=item, control_type="MenuItem")
            current.click()
            time.sleep(settings.action_delay)
        return current

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
