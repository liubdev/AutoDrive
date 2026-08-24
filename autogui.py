"""
AutoDrive 桌面版（PySide6）

启动流程：直接进入主窗口（极简主页 → 向导）
日志策略：面向用户的商业产品，日志只写入 data/logs/ 文件，界面不展示。

架构：
  UI (PySide6, 主线程)  ←引擎信号桥接→  FlowEngine (后台线程)  ←→  应用自动化 (DtsApp)

运行：python autogui.py
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from PySide6.QtWidgets import QApplication

from config.settings import settings
from ui.wizard import MainWindow


def _setup_logging():
    """日志只写文件（data/logs/autodrive_YYYYMMDD.log），不输出到控制台 / 界面"""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                            datefmt="%H:%M:%S")
    fh = logging.FileHandler(
        settings.logs_dir / f"autodrive_{datetime.now():%Y%m%d}.log",
        encoding="utf-8")
    fh.setFormatter(fmt)
    root = logging.getLogger("autodrive")
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))
    root.addHandler(fh)


def main():
    _setup_logging()

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
