"""
Screen capture - full screen and region screenshots
"""
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

import mss
from PIL import Image

from config import settings

logger = logging.getLogger("autocar.screenshot")


class ScreenCapture:

    def __init__(self):
        self._sct = mss.mss()

    def fullscreen(self, output: str = None) -> str:
        output = output or self._auto_path()
        monitor = self._sct.monitors[1]
        sct = self._sct.grab(monitor)
        Image.frombytes("RGB", sct.size, sct.rgb).save(output)
        logger.info(f"截图: {output}")
        return output

    def region(self, rect: Tuple[int, int, int, int], output: str = None) -> str:
        output = output or self._auto_path()
        monitor = {"left": rect[0], "top": rect[1],
                   "width": rect[2] - rect[0], "height": rect[3] - rect[1]}
        sct = self._sct.grab(monitor)
        Image.frombytes("RGB", sct.size, sct.rgb).save(output)
        return output

    def _auto_path(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return str(settings.reports_dir / f"screenshot_{ts}.{settings.screenshot_format}")
