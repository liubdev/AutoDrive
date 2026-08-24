"""
AutoDrive 主窗口：极简主页 + 向导面板（两级导航）

结构：
  ┌ root_stack ───────────────────────────┐
  │  0. HomePage    极简主页（开始诊断）      │
  │  1. WizardPanel ──────────────────── │
  │      顶栏：AutoDrive 品牌 + 设备状态     │
  │      步骤条：① 运行 ② 数据 ③ AI 分析     │
  │      QStackedWidget: Run / Data / Ai │
  └───────────────────────────────────────┘

引擎线程安全：FlowEngine 事件在工作线程触发 → EngineBridge(QObject) 信号
自动以 QueuedConnection 投递回主线程，UI 只响应信号。

日志策略：对用户隐藏，写入 data/logs/ 文件（autogui.py 配置），界面不展示。
注意：引擎的 logging 记录已通过 logger 继承（autodrive → FileHandler）直接落盘，
无需经 Qt 桥转发。若经桥回主线程重记，会再次触发 root 上的 _EngineLogHandler
（直接连接 → 同步递归 → RecursionError）。改日志请直接调 logging，勿走 bridge。
"""

import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from automation.apps.dts import DtsApp
from automation.flow.engine import FlowEngine
from automation.flows.dts_flow import build_dts_flow, make_output_dir
from ui.pages import AiPage, DataPage, HomePage, RunPage, _prop
from ui.report import ReportLoader
from ui.theme import ThemeManager

log = logging.getLogger("autodrive.ui.wizard")


def _safe_log(level: int, fmt: str, *args):
    """日志写入失败绝不影响主流程（文件日志是辅助，不是功能）。"""
    try:
        log.log(level, fmt, *args)
    except Exception:
        pass


# ── 设备定义（可扩展） ─────────────────────────────

DEVICES = [
    {
        "id": "dts",
        "name": "DTS 诊断仪",
        "desc": "DTS650 数据流读取 / 故障码诊断",
        "icon": "🔧",
        "class": DtsApp,
        "build_flow": build_dts_flow,
    },
]

class EngineBridge(QObject):
    """把工作线程里的引擎事件桥接到主线程（Qt 信号自动排队）"""
    flow_start = Signal(object)
    step_start = Signal(object)
    step_done = Signal(object)
    step_error = Signal(object)
    flow_done = Signal(object)
    flow_cancelled = Signal(object)
    run_finished = Signal()


class StepButton(QFrame):
    """向导步骤：圆点数字 + 标签 + 副标题，状态 done/current/next"""
    clicked = Signal(str)

    def __init__(self, number, label, sub="", step=""):
        super().__init__()
        self.setObjectName("StepBtn")
        self._step = step
        self._clickable = False
        self._number = str(number)
        self.setCursor(Qt.ArrowCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(9)
        self.dot = QLabel(self._number)
        self.dot.setObjectName("StepDot")
        self.dot.setFixedSize(22, 22)
        self.dot.setAlignment(Qt.AlignCenter)
        h.addWidget(self.dot)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.lbl = QLabel(label)
        self.lbl.setObjectName("StepLabel")
        v.addWidget(self.lbl)
        self.sub = QLabel(sub)
        self.sub.setObjectName("StepSub")
        v.addWidget(self.sub)
        h.addLayout(v)
        self.setState("next")

    def setState(self, state):
        self.dot.setText("✓" if state == "done" else self._number)
        _prop(self, "stepState", state)

    def setClickable(self, on: bool):
        self._clickable = on
        self.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)
        if on:
            self.setToolTip("点击跳转")

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit(self._step)
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("AppWindow")
        self.setWindowTitle("AutoDrive")
        self.resize(1000, 720)
        self.setMinimumSize(880, 640)

        app = QApplication.instance()
        app.setApplicationName("AutoDrive")
        app.setOrganizationName("AutoDrive")
        app.setStyle("Fusion")

        self.theme = ThemeManager(app)
        self.theme.apply()

        # 运行状态
        self._running = False
        self._cancelled = False
        self._engine = None
        self._app = None
        self._out_dir = None
        self._report_loader = ReportLoader()

        self._bridge = EngineBridge(self)
        self._build_ui()
        self._wire_bridge()
        self._goto(0)

    # ── UI 构建 ──────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 两级导航：0 主页 → 1 向导面板
        self._root_stack = QStackedWidget()
        root.addWidget(self._root_stack, 1)

        self.pages = _Pages()
        self.pages.home = HomePage()
        self.pages.home.start_requested.connect(self._start_run)
        self._root_stack.addWidget(self.pages.home)

        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(0)

        # ── 顶栏：品牌 + 设备状态 ──
        tbar = QFrame()
        tbar.setObjectName("TBar")
        tbar.setFixedHeight(46)
        th = QHBoxLayout(tbar)
        th.setContentsMargins(18, 0, 14, 0)
        th.setSpacing(0)
        b1 = QLabel("Auto")
        b1.setObjectName("Brand")
        b2 = QLabel("Drive")
        b2.setObjectName("BrandAcc")
        th.addWidget(b1)
        th.addWidget(b2)
        th.addSpacing(14)
        self._dev_status = QLabel("○ 就绪")
        self._dev_status.setObjectName("DevStatus")
        th.addWidget(self._dev_status)
        th.addStretch(1)
        pv.addWidget(tbar)

        # ── 步骤条 ──
        wizbar = QFrame()
        wizbar.setObjectName("WizBar")
        wh = QHBoxLayout(wizbar)
        wh.setContentsMargins(16, 6, 16, 6)
        wh.setSpacing(2)
        wh.addStretch(1)
        self._step_btns = []
        specs = [("1", "运行", "运行 DTS 流程", "run"),
                 ("2", "数据", "故障码 / 数据流 / 文件", "data"),
                 ("3", "AI 分析", "摘要 / 原因 / 方案", "ai")]
        for i, (num, label, sub, key) in enumerate(specs):
            if i:
                conn = QFrame()
                conn.setObjectName("Conn")
                conn.setFixedSize(30, 2)
                wh.addWidget(conn)
            btn = StepButton(num, label, sub, key)
            btn.clicked.connect(self._on_step_clicked)
            self._step_btns.append(btn)
            wh.addWidget(btn)
        wh.addStretch(1)
        pv.addWidget(wizbar)

        # ── 页面 ──
        self._stack = QStackedWidget()
        self.pages.run = RunPage()
        self.pages.data = DataPage()
        self.pages.ai = AiPage()
        self.pages.run.cancel_requested.connect(self._cancel_run)
        self.pages.run.back_requested.connect(self._go_home)
        for p in (self.pages.run, self.pages.data, self.pages.ai):
            self._stack.addWidget(p)
        pv.addWidget(self._stack, 1)

        self._root_stack.addWidget(panel)

    def _wire_bridge(self):
        b = self._bridge
        b.flow_start.connect(self._on_flow_start)
        b.step_start.connect(self._on_step_start)
        b.step_done.connect(self._on_step_done)
        b.step_error.connect(self._on_step_error)
        b.flow_done.connect(self._on_flow_done)
        b.flow_cancelled.connect(self._on_flow_cancelled)
        b.run_finished.connect(self._on_run_finished)

    # ── 向导导航 ─────────────────────────────────

    def _step_index(self, key: str) -> int:
        return {"run": 0, "data": 1, "ai": 2}[key]

    def _on_step_clicked(self, key: str):
        idx = self._step_index(key)
        if idx != self._stack.currentIndex():
            self._goto(idx)

    def _goto(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._step_btns):
            state = "current" if i == idx else ("done" if i < idx else "next")
            btn.setState(state)

    def _go_home(self):
        if self._running:
            return
        self._root_stack.setCurrentIndex(0)

    # ── 运行流程 ─────────────────────────────────

    def _start_run(self):
        if self._running:
            return
        dev = DEVICES[0]
        self._running = True
        self._cancelled = False
        self._dev_status.setText("● 执行中")
        self.pages.home.set_busy(True)

        app = dev["class"]()
        self._app = app
        self._out_dir = make_output_dir()
        _safe_log(logging.INFO, "输出目录: %s", self._out_dir)

        self._engine = FlowEngine()
        self._engine.steps = dev["build_flow"](app, self._out_dir)
        self._wire_engine(self._engine)

        page = self.pages.run
        page.reset_steps(self._engine.steps)
        page.set_running(True)
        page.set_status(f"启动 {dev['name']} 自动化…")

        # 进入向导面板并从第一步开始执行
        self._root_stack.setCurrentIndex(1)
        self._goto(0)
        threading.Thread(target=self._run_engine, daemon=True).start()

    def _wire_engine(self, eng: FlowEngine):
        b = self._bridge
        eng.on("flow_start", b.flow_start.emit)
        eng.on("step_start", b.step_start.emit)
        eng.on("step_done", b.step_done.emit)
        eng.on("step_error", b.step_error.emit)
        eng.on("flow_done", b.flow_done.emit)
        eng.on("flow_cancelled", b.flow_cancelled.emit)

    def _run_engine(self):
        try:
            self._engine.run(verify_app=self._app)
        except Exception as e:
            _safe_log(logging.ERROR, "执行异常: %s", e)
        finally:
            try:
                self._app.disconnect()
            except Exception:
                pass
            self._bridge.run_finished.emit()

    def _cancel_run(self):
        if self._engine and not self._engine.done:
            self._engine.cancel()
            self._cancelled = True
            self.pages.run.set_status("正在取消…")

    # ── 引擎事件（主线程） ────────────────────────

    def _on_flow_start(self, engine):
        self.pages.run.set_status("开始执行…")

    def _on_step_start(self, step):
        self.pages.run.render_steps()
        self.pages.run.set_status(f"正在执行: {step.name}")

    def _on_step_done(self, step):
        self.pages.run.render_steps()

    def _on_step_error(self, step):
        self.pages.run.render_steps()
        self.pages.run.set_status(f"步骤失败: {step.name}")

    def _on_flow_done(self, engine):
        self.pages.run.render_steps()
        self.pages.run.set_status("流程完成 — 正在整理数据…")
        self._load_report(advance=True)

    def _on_flow_cancelled(self, engine):
        self.pages.run.render_steps()
        self.pages.run.set_status("流程已取消")
        self._load_report(advance=False)

    def _on_run_finished(self):
        self._running = False
        self.pages.home.set_busy(False)
        self.pages.run.set_running(False)
        self._dev_status.setText("○ 就绪")

    # ── 报告加载 → 数据 / AI 页 ───────────────────

    def _load_report(self, advance: bool):
        if not self._out_dir:
            return
        report = self._report_loader.load(self._out_dir)
        self.pages.data.set_report(report)
        self.pages.ai.set_report(report)
        if report.has_data:
            self._step_btns[1].setClickable(True)
            self._step_btns[2].setClickable(True)
            if advance:
                self._goto(1)


class _Pages:
    """占位容器，运行期注入页面引用"""
    pass
