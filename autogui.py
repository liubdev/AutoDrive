"""
AutoDrive 桌面版（PySide6）

启动流程：主页·设备选择（ct1：选车型卡 + 常见问题 + DTS 诊断仪·运行）→ 分析页（ct2：描述问题 → 采集 + AI 诊断 → 维修报告）
日志策略：面向用户的商业产品，日志只写入 data/logs/ 文件，界面不展示。

架构：
  UI (PySide6, 主线程)  ←引擎信号桥接→  FlowEngine (后台线程)  ←→  应用自动化 (DtsApp)

运行：python autogui.py
"""

import faulthandler
import logging
import threading
import ctypes
import subprocess
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
    return fh


def _is_admin() -> bool:
    """Return whether the current process has an elevated administrator token."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _relaunch_as_admin() -> bool:
    """Relaunch this source script or frozen executable through the UAC prompt."""
    if getattr(sys, "frozen", False):
        executable = str(Path(sys.executable).resolve())
        parameters = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = str(Path(sys.executable).resolve())
        parameters = subprocess.list2cmdline([str(Path(__file__).resolve()), *sys.argv[1:]])
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, parameters, str(_HERE), 1
        )
        return result > 32
    except OSError:
        return False


def _ask_admin_startup(app: "QApplication") -> bool:
    """Ask once at startup; return False when the relaunch request was accepted."""
    from PySide6.QtWidgets import QMessageBox

    if _is_admin():
        return True
    choice = QMessageBox.question(
        None,
        "启动权限确认",
        "AutoDrive 需要管理员权限才能稳定启动 DTS 诊断仪。\n\n"
        "是否现在以管理员身份重新启动？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if choice != QMessageBox.StandardButton.Yes:
        return True
    if _relaunch_as_admin():
        return False
    QMessageBox.warning(
        None,
        "管理员启动失败",
        "未能以管理员身份重新启动。程序将继续以当前权限运行，\n"
        "如果 DTS 无法启动，请右键 AutoDrive 选择“以管理员身份运行”。",
    )
    return True


def _record_exception(exc_type, exc_value, exc_tb):
    logging.getLogger("autodrive.startup").critical(
        "未处理的 Python 异常", exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    handler = _setup_logging()
    log = logging.getLogger("autodrive.startup")
    sys.excepthook = _record_exception
    threading.excepthook = lambda args: _record_exception(
        args.exc_type, args.exc_value, args.exc_traceback)
    log.info("启动开始：Python=%s；解释器=%s；日志=%s",
             sys.version.replace("\n", " "), sys.executable, handler.baseFilename)
    # FileHandler 在整个进程期间保持打开，原生崩溃栈也写入同一份日志。
    watchdog = False
    try:
        faulthandler.enable(file=handler.stream, all_threads=True)
        faulthandler.dump_traceback_later(30, file=handler.stream)
        watchdog = True
    except Exception:
        log.exception("无法启用原生崩溃或启动超时堆栈记录")
    try:
        log.info("启动阶段：导入 PySide6")
        from PySide6.QtCore import QCoreApplication, QEasingCurve, QPropertyAnimation, Qt, qInstallMessageHandler
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication, QDialog

        def qt_message(kind, context, message):
            logging.getLogger("autodrive.qt").warning("%s: %s", kind, message)

        qInstallMessageHandler(qt_message)

        log.info("启动阶段：创建 QApplication")
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        if watchdog:
            faulthandler.cancel_dump_traceback_later()
        log.info("启动阶段：管理员权限确认")
        if not _ask_admin_startup(app):
            log.info("已请求提权重启，当前进程正常退出")
            return 0
        if watchdog:
            faulthandler.dump_traceback_later(30, file=handler.stream)
        icon_path = (_HERE / "icon.ico")
        if getattr(sys, "frozen", False):
            icon_path = Path(sys.executable).resolve().parent / "icon.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        # 延迟导入：必须在 QApplication 之后 import ui.wizard（会拉入 pywinauto/comtypes 链）。
        # 先建 QApplication 让 Qt 拥有主线程 COM(STA)，否则该链会抢先以 MTA 初始化 COM，
        # 导致 Qt OleInitialize() 失败 (0x80010106)。
        log.info("启动阶段：导入 ui.wizard")
        from ui.wizard import MainWindow
        log.info("启动阶段：导入 ui.auth")
        from ui.auth import LoginDialog

        log.info("启动阶段：创建 MainWindow")
        win = MainWindow()
        # 登录阶段不显示未认证的客户端内容，登录成功后再打开主界面。
        log.info("启动阶段：创建登录窗口")
        login = LoginDialog()
        if watchdog:
            faulthandler.cancel_dump_traceback_later()
        log.info("等待用户登录")
        if login.exec() != QDialog.DialogCode.Accepted:
            log.info("登录未通过或已取消，程序正常退出")
            return 0
        log.info("登录成功，显示主窗口")
        win.setWindowOpacity(0.0)
        win.show()
        show_anim = QPropertyAnimation(win, b"windowOpacity", win)
        show_anim.setDuration(280)
        show_anim.setStartValue(0.0)
        show_anim.setEndValue(1.0)
        show_anim.setEasingCurve(QEasingCurve.OutCubic)
        win._show_anim = show_anim
        show_anim.start()
        log.info("进入主窗口事件循环")
        code = app.exec()
        log.info("程序退出：Qt 返回码=%s", code)
        return code
    except Exception:
        log.exception("启动或运行失败")
        return 1
    finally:
        if watchdog:
            faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    sys.exit(main())
