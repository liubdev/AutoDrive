"""
AutoDrive 主窗口：极简主页 + 单页连续诊断流（两级导航）

结构：
  ┌ root_stack ───────────────────────────┐
  │  0. HomePage    极简主页（开始诊断）      │
  │  1. DiagnosticPanel ──────────────── │
  │      顶栏：AutoDrive 品牌 + 设备状态     │
  │      PhaseBar：①采集 ②数据 ③AI 进度指示  │
  │      DiagnosticPage（单页滚动，随流程展开）│
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

from PySide6.QtCore import QObject, Signal
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
from ui.pages import DiagnosticPage, HomePage, PhaseBar
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


class AiBridge(QObject):
    """AI 诊断链事件桥（工作线程 → 主线程）"""
    stage_started = Signal(int, str)         # (stage_no, name)
    stage_done = Signal(int, str, object)    # (stage_no, name, result_obj)
    ai_failed = Signal(str)                  # 用户可读错误
    ai_finished = Signal(object)             # {"plan","locatability","report","out_dir"}


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
        self._ai_running = False
        self._pending_auto_ai = False   # 采集完成且有诊断数据 → 自动启动 AI 分析
        self._engine = None
        self._app = None
        self._out_dir = None
        self._report_loader = ReportLoader()

        self._bridge = EngineBridge(self)
        self._ai_bridge = AiBridge(self)
        self._build_ui()
        self._wire_bridge()
        self._root_stack.setCurrentIndex(0)

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

        # ── 进度指示（纯展示，不可点击） ──
        self._phase_bar = PhaseBar()
        pv.addWidget(self._phase_bar)

        # ── 单页连续诊断流（①采集→②数据→③AI 全在一页，随流程展开） ──
        self.pages.diag = DiagnosticPage()
        # 保留别名，让既有调用点（wizard 内部 + 冒烟测试）零改动
        self.pages.run = self.pages.diag.run
        self.pages.data = self.pages.diag.data
        self.pages.ai = self.pages.diag.ai
        self.pages.diag.start_requested.connect(self._start_ai_diagnosis)
        self.pages.diag.cancel_requested.connect(self._cancel_run)
        self.pages.diag.back_requested.connect(self._go_home)
        pv.addWidget(self.pages.diag, 1)

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

        ab = self._ai_bridge
        ab.stage_started.connect(self._on_ai_stage_started)
        ab.stage_done.connect(self._on_ai_stage_done)
        ab.ai_failed.connect(self._on_ai_failed)
        ab.ai_finished.connect(self._on_ai_finished)

    # ── 流程阶段指示 ────────────────────────────────

    def _set_phase(self, phase: str):
        """phase ∈ "run" | "data" | "ai"，同步顶部进度条"""
        self._phase_bar.set_phase(phase)

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
        self.pages.diag.reset_all()
        page.reset_steps(self._engine.steps)
        page.set_running(True)
        page.set_status(f"启动 {dev['name']} 自动化…")

        # 进入单页诊断流并从采集阶段开始
        self._root_stack.setCurrentIndex(1)
        self._set_phase("run")
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
        report = self._load_report(advance=True)
        # 有故障码或数据流 → 待运行线程收尾后自动启动 AI 分析
        self._pending_auto_ai = bool(report and (report.faults or report.flows))

    def _on_flow_cancelled(self, engine):
        self.pages.run.render_steps()
        self.pages.run.set_status("流程已取消")
        self._pending_auto_ai = False
        self._load_report(advance=False)

    def _on_run_finished(self):
        self._running = False
        self.pages.home.set_busy(False)
        self.pages.run.set_running(False)
        self._dev_status.setText("○ 就绪")
        if self._pending_auto_ai:
            self._pending_auto_ai = False
            self._start_ai_diagnosis(auto=True)

    # ── 报告加载 → 数据 / AI 页 ───────────────────

    def _load_report(self, advance: bool):
        if not self._out_dir:
            return None
        report = self._report_loader.load(self._out_dir)
        self.pages.diag.set_report(report)
        if report.has_data and advance:
            # 自动跟随当前阶段：滚到「采集结果」摘要，方便紧接着发起 AI 诊断
            self._set_phase("data")
            self.pages.diag.scroll_to(self.pages.diag._data_section)
        return report


    # ── AI 诊断（三阶段链路） ──────────────────────

    def _start_ai_diagnosis(self, auto: bool = False):
        """auto=True：采集完成后自动触发，症状留空走 build_slots 自动兜底。"""
        if self._running or self._ai_running:
            return
        if not self._out_dir:
            self.pages.ai.show_error("尚未生成报告，请先运行一次 DTS 流程")
            return
        if auto:
            symptom, notes = "", ""   # 自动模式：以故障码为依据推断
        else:
            symptom, notes = self.pages.ai.get_input()
            if not symptom:
                self.pages.ai.show_error("请先填写故障现象")
                return

        from ai.deepseek import DeepSeekClient
        client = DeepSeekClient()
        if not client.configured:
            if auto:
                # 自动模式未配置 key：软跳过，不打断采集收尾
                self.pages.ai.set_status(
                    "未配置 DeepSeek API Key，自动诊断已跳过；配置后再次运行将自动分析")
                self._dev_status.setText("○ 就绪")
                return
            self.pages.ai.show_error(
                "未配置 DeepSeek API Key（环境变量 DEEPSEEK_API_KEY 或 data/config.json 的 api_key）")
            return

        self._ai_running = True
        report = self._report_loader.load(self._out_dir)
        self.pages.ai.set_report(report)
        self.pages.ai.reset()
        self.pages.ai.set_running(True)
        self.pages.ai.set_status("正在确认采集列表…")
        self._dev_status.setText("● AI 分析中")
        self._set_phase("ai")
        self.pages.diag.scroll_to(self.pages.diag.ai)

        threading.Thread(
            target=self._run_ai_chain,
            args=(report, symptom, notes, client),
            daemon=True,
        ).start()

    def _run_ai_chain(self, report, symptom, notes, client):
        from ai import AiDiagnosticChain
        from ai.deepseek import AiError

        chain = AiDiagnosticChain(client=client)

        def stage_start(no, name):
            self._ai_bridge.stage_started.emit(no, name)

        def stage_done(no, name, obj):
            self._ai_bridge.stage_done.emit(no, name, obj)

        try:
            result = chain.run_full(
                report, symptom, notes,
                callbacks={"stage_start": stage_start, "stage_done": stage_done})
            self._ai_bridge.ai_finished.emit(result)
        except AiError as e:
            _safe_log(logging.ERROR, "AI 诊断失败: %s", e)
            self._ai_bridge.ai_failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            _safe_log(logging.ERROR, "AI 诊断异常: %s", e)
            self._ai_bridge.ai_failed.emit(f"AI 诊断异常：{e}")

    def _on_ai_stage_started(self, no, name):
        self.pages.ai.set_stage(no, "running", "分析中…")

    def _on_ai_stage_done(self, no, name, obj):
        if no == 1:
            self.pages.ai.set_stage(1, "done", "完成")
            self.pages.ai.show_plan(obj.asdict())
            self.pages.ai.set_status("采集计划已生成，正在判断是否需要路试…")
            self.pages.diag.scroll_to(self.pages.ai._plan_card_ref())
        elif no == 2:
            self.pages.ai.set_stage(2, "done", "完成")
            self.pages.ai.show_locatability(obj.asdict())
            self.pages.ai.set_status("路试判断完成，正在输出维修报告…")
            self.pages.diag.scroll_to(self.pages.ai._loc_card_ref())
        elif no == 3:
            self.pages.ai.set_stage(3, "done", "完成")
            self.pages.ai.show_report(obj)
            self.pages.diag.scroll_to(self.pages.ai._report_card_ref())

    def _on_ai_finished(self, result):
        self._ai_running = False
        self.pages.ai.set_running(False)
        self.pages.ai.set_status("诊断完成 — 可查看采集计划 / 路试判断 / 维修报告")
        self._dev_status.setText("○ 就绪")

    def _on_ai_failed(self, msg):
        self._ai_running = False
        self.pages.ai.set_running(False)
        self.pages.ai.show_error(msg)
        self._dev_status.setText("○ 就绪")


class _Pages:
    """占位容器，运行期注入页面引用"""
    pass
