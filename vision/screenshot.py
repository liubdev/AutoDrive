"""
Screen capture - full screen, region, element, and window screenshots
"""
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

import mss
from PIL import Image

from config import settings
from automation.locator import Element

logger = logging.getLogger("autocar.screenshot")


class ScreenCapture:
    """Screen capture utility"""

    def __init__(self):
        self._sct = mss.mss()

    def fullscreen(self, output: str = None) -> str:
        """
        Full-screen screenshot

        Args:
            output: save path (auto-generated if not given)
        Returns:
            file path
        """
        output = output or self._auto_path()
        monitor = self._sct.monitors[1]
        sct = self._sct.grab(monitor)
        img = Image.frombytes("RGB", sct.size, sct.rgb)
        img.save(output)
        logger.info(f"Full screenshot: {output}")
        return output

    def region(self, rect: Tuple[int, int, int, int], output: str = None) -> str:
        """
        Capture a specific region

        Args:
            rect: (left, top, right, bottom)
            output: save path
        """
        output = output or self._auto_path()
        monitor = {"left": rect[0], "top": rect[1],
                   "width": rect[2] - rect[0], "height": rect[3] - rect[1]}
        sct = self._sct.grab(monitor)
        img = Image.frombytes("RGB", sct.size, sct.rgb)
        img.save(output)
        logger.info(f"Region screenshot: {output}")
        return output

    def element(self, element: Element, output: str = None,
                padding: int = 2) -> str:
        """
        Capture a specific element

        Args:
            element: UI element
            padding: extra pixels around the element
        """
        rect = element.rect
        return self.region(
            (rect[0] - padding, rect[1] - padding,
             rect[2] + padding, rect[3] + padding),
            output
        )

    def active_window(self, output: str = None) -> Optional[str]:
        """Capture the active window"""
        try:
            import pywinauto
            desktop = pywinauto.Desktop(backend=settings.uia_backend)
            active = desktop.windows()[0]
            r = active.rectangle  # property, not method
            return self.region((r.left, r.top, r.right, r.bottom), output)
        except Exception as e:
            logger.error(f"Window capture failed: {e}")
            return None

    def _auto_path(self) -> str:
        """Auto-generate screenshot filename"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = settings.reports_dir / f"screenshot_{ts}.{settings.screenshot_format}"
        return str(path)
