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

        # Infer window title hint from executable name
        exe_name = Path(path).stem.lower()
        title_keywords = {
            "notepad": "记事本",
            "mspaint": "画图",
            "calc": "计算器",
            "explorer": "文件资源管理器",
            "cmd": "命令提示符",
            "powershell": "Windows PowerShell",
        }
        title_hint = title_keywords.get(exe_name, exe_name)

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
                # Strategy 1: match by PID
                matched = [w for w in wins if w.process_id == proc.pid]
                # Strategy 2: match by executable name in window class/title
                if not matched:
                    matched = [
                        w for w in wins
                        if (w.name and exe_name.lower() in w.name.lower())
                        or (w.class_name and exe_name.lower() in w.class_name.lower())
                    ]
                # Strategy 3: match by well-known title keywords
                if not matched:
                    matched = [
                        w for w in wins
                        if w.name and title_hint.lower() in w.name.lower()
                    ]

                if matched:
                    matched_window = matched[0]
                    break
            except Exception:
                pass

            time.sleep(0.5)

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
        kwargs = {"backend": settings.uia_backend}
        if pid:
            kwargs["process"] = pid
        elif handle:
            kwargs["handle"] = handle
        elif path:
            kwargs["path"] = path
        elif title:
            wins = find_elements(backend=settings.uia_backend, top_level_only=True)
            for w in wins:
                if title.lower() in (w.name or "").lower():
                    kwargs["handle"] = w.handle
                    break
            if "handle" not in kwargs:
                raise LookupError(f"No window found with title containing '{title}'")

        self._app = Application(**kwargs)
        self._app.connect(**{k: v for k, v in kwargs.items() if k != "backend"})
        logger.info(f"Connected to process (pid={pid}, path={path})")
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

    def close(self):
        """Safely close the window"""
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
