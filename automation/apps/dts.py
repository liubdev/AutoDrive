import time
import logging
from pathlib import Path
from typing import Optional

from pywinauto.findwindows import find_elements
import psutil

from . import BaseApp

logger = logging.getLogger("autocar.apps.dts")


class DtsApp(BaseApp):

    APP_EXE = r"C:\Program Files (x86)\DTS\DTS20220525\DTS650.exe"
    INSTANCE_MULTI = False

    # ── 生命周期 ──────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self._repo_name = ""
