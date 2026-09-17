"""
AutoDrive 桌面版（PySide6）

启动流程：主页·设备选择（ct1：选车型卡 + 常见问题 + DTS 诊断仪·运行）→ 分析页（ct2：描述问题 → 采集 + AI 诊断 → 维修报告）
日志策略：面向用户的商业产品，日志只写入 data/logs/ 文件，界面不展示。

架构：
  UI (PySide6, 主线程)  ←引擎信号桥接→  FlowEngine (后台线程)  ←→  应用自动化 (DtsApp)

运行：python autogui.py
"""

import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

# pywinauto 导入时若发现主线程 COM 为 MTA，会自行退回 STA 并打印一条
# 无害告警（"Revert to STA COM threading mode"）。静默它，保持启动输出干净。
warnings.filterwarnings("ignore", message="Revert to STA COM threading mode")

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from config.settings import settings


def _setup_logging():
    """日志只写文件（data/logs/autodrive_YYYYMMDD.log），不输出到控制台 / 界面。

    FileHandler 挂在根 logger 上 —— 自动化链 (autocar.*) 与产品链 (autodrive.*)
    都向上传播到根，统一落盘到同一个每日文件。此前挂在 autodrive 上，
    DTS 自动化 (autocar.apps.dts / autocar.apps / autocar.vision.*) 的日志会全部丢失。
    """
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                            datefmt="%H:%M:%S")
    fh = logging.FileHandler(
        settings.logs_dir / f"autodrive_{datetime.now():%Y%m%d}.log",
        encoding="utf-8")
    fh.setFormatter(fmt)
    root = logging.getLogger()  # 根：autodrive.* 与 autocar.* 都落盘
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))
    root.addHandler(fh)


def main():
    _setup_logging()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = (_HERE / "icon.ico")
    if getattr(sys, "frozen", False):
        icon_path = Path(sys.executable).resolve().parent / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 延迟导入：必须在 QApplication 之后 import ui.wizard（会拉入 pywinauto/comtypes 链）。
    # 先建 QApplication 让 Qt 拥有主线程 COM(STA)，否则该链会抢先以 MTA 初始化 COM，
    # 导致 Qt OleInitialize() 失败 (0x80010106)。
    from ui.wizard import MainWindow
    from ui.auth import LoginDialog

    win = MainWindow()
    # 登录阶段不显示未认证的客户端内容，登录成功后再打开主界面。
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        return
    win.setWindowOpacity(0.0)
    win.show()
    show_anim = QPropertyAnimation(win, b"windowOpacity", win)
    show_anim.setDuration(280)
    show_anim.setStartValue(0.0)
    show_anim.setEndValue(1.0)
    show_anim.setEasingCurve(QEasingCurve.OutCubic)
    win._show_anim = show_anim
    show_anim.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
