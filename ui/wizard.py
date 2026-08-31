"""
远驰科技 · 智能诊断平台 主窗口：AppShell 外壳 + 19 页 + DTS/AI 真实链路接线。

结构：
  MainWindow(QMainWindow)
    AppShell: TBar(品牌 + 页标题 + 设备状态 + 时钟 + 退出)
              QStackedWidget（19 页：home / ai-diagn / report / settings / account /
                                 remote* / special* / ebs* / can / update）
              BBar(账户按钮 + 上下文按钮，goPage 时重建)

进入流程：主页选设备 + 选故障现象/输入问题 → 底栏「开始AI智能诊断」→ ai-diagn 页：
  · 设备名含「DTS」→ DTS650 自动化采集（后台线程）→ 有数据 → DeepSeek 三阶段 AI；
  · 其余设备 / 无真机 → 演示数据降级填充。

引擎线程安全：FlowEngine 事件在工作线程触发 → EngineBridge(QObject) 信号
自动以 QueuedConnection 投递回主线程，UI 只响应信号。AI 三阶段经 AiBridge 同理。

日志策略：对用户隐藏，写入 data/logs/ 文件（autogui.py 配置），界面不展示。
注意：引擎的 logging 记录已通过 logger 继承（autodrive → FileHandler）直接落盘，
无需经 Qt 桥转发。若经桥回主线程重记，会再次触发 root 上的 _EngineLogHandler
（直接连接 → 同步递归 → RecursionError）。改日志请直接调 logging，勿走 bridge。
"""

import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from automation.apps.dts import DtsApp
from automation.flow.engine import FlowEngine
from automation.flows.dts_flow import build_dts_flow, make_output_dir
from ui.appshell import AppShell
from ui.lcsdata import DEMO_VEHICLE, DIAG_STEPS, DYN_MSGS, EBS_DTC
from ui.pages import PAGE_REGISTRY
from ui.report import ReportLoader, build_demo_ai_report, build_demo_report
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
    """诊断分析链事件桥（工作线程 → 主线程）"""
    stage_started = Signal(int, str)         # (stage_no, name)
    stage_done = Signal(int, str, object)    # (stage_no, name, result_obj)
    ai_failed = Signal(str)                  # 用户可读错误
    ai_finished = Signal(object)             # {"plan","locatability","report","out_dir"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("AppWindow")
        self.setWindowTitle("远驰科技 · 智能诊断平台")
        self.resize(1000, 720)
        self.setMinimumSize(900, 640)

        app = QApplication.instance()
        app.setApplicationName("AutoDrive")
        app.setOrganizationName("AutoDrive")
        app.setStyle("Fusion")

        self.theme = ThemeManager(app)
        # 运行状态
        self._running = False
        self._cancelled = False
        self._ai_running = False
        self._pending_auto_ai = False   # 采集完成且有诊断数据 → 自动启动诊断分析
        self._pending_symptom = ""      # 发送时捕获的故障现象（自动 AI 阶段用）
        self._pending_notes = ""
        self._device = None             # 主页选中的设备 dict
        self._symptoms = []             # 选中故障现象
        self._engine = None
        self._app = None
        self._out_dir = None
        self._report_loader = ReportLoader()

        self._bridge = EngineBridge(self)
        self._ai_bridge = AiBridge(self)
        self._build_ui()
        self._wire_bridge()
        # 页面就绪后再应用主题：apply() 需对所有已存在 widget 打 ui/mode 属性
        self.theme.apply()
        self._set_phase("run")
        # 启动即按屏幕可用区居中（availableGeometry 已扣除任务栏）
        try:
            scr = QApplication.instance().screenAt(self.pos()) or QApplication.primaryScreen()
            geo = scr.availableGeometry()
            self.move(geo.center() - self.rect().center())
        except Exception:
            pass

    # ── UI 构建 ──────────────────────────────────

    def _ensure_page(self, pid):
        """懒加载页面：首次 goPage 才构建，注入 shell + 应用主题属性。

        eager 3 页（home/ai-diagn/settings）在 _build_ui 里预构建；其余 16 页
        首次进入时构建 → 启动只需建 3 页，theme.apply() 也只刷 3 页。
        """
        cls = PAGE_REGISTRY.get(pid)
        if cls is None:
            return None
        page = self.pages.get(pid)
        if page is not None:
            return page
        page = cls()
        page.shell = self.shell
        self.theme.apply_to(page)
        self.pages[pid] = page
        return page

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # AppShell：顶栏 + 页面栈 + 底栏
        self.shell = AppShell()
        root.addWidget(self.shell)

        # 懒加载注册表（其余 16 页由 goPage 首次触发构建）
        self.pages: dict = {}
        self.shell.set_page_resolver(self._ensure_page)

        # 核心页立即构建：home 落地页 / ai-diagn 程序化调用 / settings 信号连线
        for pid in ("home", "ai-diagn", "settings"):
            self._ensure_page(pid)

        self.home = self.pages["home"]
        self.ai_diag = self.pages["ai-diagn"]

        # 兼容别名（旧 wizard / 测试引用点）
        self._stack = self.shell.stack
        self._phase_bar = self.ai_diag._steps_bar   # 四节点步进器
        self._dev_status = self.shell._dev_status   # 顶栏设备状态胶囊

        # 信号接线
        self.shell.nav_requested.connect(self._on_action)
        self.shell.exit_requested.connect(self._confirm_exit)
        self.pages["settings"].theme_requested.connect(self.theme.set_theme)
        self.ai_diag.restart_requested.connect(self._on_restart)
        self.ai_diag.export_requested.connect(self._export_ai_report)

        # 启动即主页
        self.shell.goPage("home")

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

    # ── 动作分发（底栏 / 顶栏按钮） ────────────────

    def _on_action(self, act, page):
        handlers = {
            "startAi": self._on_start_ai,
            "exitApp": self._confirm_exit,
            "logout": lambda: self.shell.toast("已退出登录（演示）"),
            "dtcHelp": lambda: self.shell.toast("故障码帮助：点击故障码行可查看详情（演示）"),
            "dtcCopy": self._copy_dtc,
            "dtcAi": lambda: self.shell.toast("AI 故障码分析演示中，真实诊断请使用 DTS 设备"),
            "dfRestart": self._dataflow_restart,
            "dfFast": lambda: self._dataflow_speed(100, "采样已加快"),
            "dfSlow": lambda: self._dataflow_speed(400, "采样已放慢"),
            "dfPause": self._dataflow_pause,
            "runTest": lambda: self.shell.toast("已发起测试（演示）"),
            "clearCache": lambda: self.shell.toast("已清理 24.6 MB 缓存"),
            "attach": lambda: self.shell.toast("图片上传功能演示中"),
            "voice": lambda: self.shell.toast("语音输入功能演示中"),
            "reactivate": lambda: self.shell.toast("已重新激活连接 ID"),
            "remoteConn": lambda: self.shell.toast("正在连接…（演示）"),
            "cancelRemote": self._on_cancel_remote,
        }
        handler = handlers.get(act)
        if handler:
            handler()
        else:
            self.shell.toast("演示功能")

    def _copy_dtc(self):
        codes = "\n".join(f"{r[0]}  {r[1]}" for r in EBS_DTC)
        QApplication.clipboard().setText(codes)
        self.shell.toast(f"已复制 {len(EBS_DTC)} 条故障码")

    def _dataflow_restart(self):
        p = self.pages.get("ebs-dataflow")
        if p is not None:
            p._tick = 0
            p._timer.start(200)
        self.shell.toast("数据流已重启")

    def _dataflow_speed(self, ms, msg):
        p = self.pages.get("ebs-dataflow")
        if p is not None:
            p._timer.setInterval(ms)
        self.shell.toast(msg)

    def _dataflow_pause(self):
        p = self.pages.get("ebs-dataflow")
        if p is not None:
            p._timer.stop()
        self.shell.toast("数据流已暂停")

    def _on_cancel_remote(self):
        self.shell.goPage("remote")
        self.shell.toast("已取消远程控制")

    def _confirm_exit(self):
        self.shell.show_modal("退出应用", "确定要退出远驰科技智能诊断平台吗？",
                              ok_text="退出", on_ok=QApplication.instance().quit)

    # ── 流程阶段指示 ────────────────────────────────

    def _set_phase(self, phase: str):
        """phase ∈ "run" | "data" | "ai" | "report"，同步四节点步进器"""
        self._phase_bar.set_phase(phase)

    # ── 入口：底栏「开始AI智能诊断」 ─────────────────

    def _on_start_ai(self):
        """校验输入 → 进入 ai-diagn 页 → DTS 走真实采集链路，其余走演示降级。"""
        if self._running or self._ai_running:
            return
        dev = self.home.selected_device()
        if not dev:
            self.shell.toast("请先选择设备", "crit")
            return
        if not self.home.has_input():
            self.shell.toast("请先选择故障现象或输入车辆问题", "crit")
            return

        self._device = dev
        self._symptoms = self.home.selected_symptoms()
        q = self.home.question_text()
        self._pending_symptom = q or "；".join(self._symptoms)
        self._pending_notes = ""

        self.ai_diag.set_summary(dev["n"], self._pending_symptom)
        self.ai_diag.reset()
        self._set_phase("run")
        self.shell.goPage("ai-diagn")

        if "DTS" in (dev.get("n") or "").upper():
            self._start_dts_collection()
        else:
            self._run_demo_diagnosis(f"「{dev['n']}」暂未接入自动化，已使用演示数据填充")

    # ── DTS 真实链路：采集 ─────────────────────────

    def _start_dts_collection(self):
        """DTS650 自动化采集（后台线程，事件经 EngineBridge 回主线程）。"""
        if self._running:
            return
        dev = DEVICES[0]
        self._running = True
        self._cancelled = False
        self._dev_status.setText("● 执行中")
        self.ai_diag.set_running(True)
        self.ai_diag.set_status(f"启动 {dev['name']} 自动化…")

        app = dev["class"]()
        self._app = app
        self._out_dir = make_output_dir()
        _safe_log(logging.INFO, "输出目录: %s", self._out_dir)

        self._engine = FlowEngine()
        self._engine.steps = dev["build_flow"](app, self._out_dir)
        self._wire_engine(self._engine)
        self._set_phase("ai")
        self.ai_diag.append_dyn("正在与车辆通讯中...")
        self.ai_diag.set_dyn_status("识别中")
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

    # ── 引擎事件（主线程） ────────────────────────

    def _on_flow_start(self, engine):
        self.ai_diag.append_dyn("正在与车辆通讯中...")
        self.ai_diag.set_dyn_status("识别中")

    def _on_step_start(self, step):
        name = getattr(step, "name", "") or ""
        upper = name.upper()
        if "OBD" in upper:
            self.ai_diag.append_dyn("正在识别OBD信息...")
        elif "VIN" in upper or "车辆" in name:
            self.ai_diag.append_dyn("正在识别车辆信息...")
        elif "发动机" in name or "ECU" in upper:
            self.ai_diag.append_dyn("正在识别发动机信息...")
        self.ai_diag.set_dyn_status(f"正在执行: {name}")

    def _on_step_done(self, step):
        pass

    def _on_step_error(self, step):
        self.ai_diag.append_dyn(f"步骤失败: {step.name}", cls="error")

    def _on_flow_done(self, engine):
        self.ai_diag.append_dyn("数据采集完成，正在整理数据…", cls="done")
        report = self._load_report(advance=True)
        # 有故障码或数据流 → 待运行线程收尾后自动启动诊断分析
        self._pending_auto_ai = bool(report and (report.faults or report.flows))

    def _on_flow_cancelled(self, engine):
        self.ai_diag.append_dyn("流程已取消", cls="error")
        self._pending_auto_ai = False
        self._load_report(advance=False)

    def _on_run_finished(self):
        self._running = False
        self.ai_diag.set_running(False)
        self._dev_status.setText("○ 就绪")
        if self._pending_auto_ai:
            self._pending_auto_ai = False
            self._start_ai_diagnosis(auto=True)
        else:
            # 无真机 / 采集空 → 演示降级
            self._run_demo_diagnosis("未检测到诊断数据，已填充演示数据")

    # ── 报告加载 → ai-diagn 页 ───────────────────

    def _load_report(self, advance: bool):
        if not self._out_dir:
            return None
        report = self._report_loader.load(self._out_dir)
        self.ai_diag.set_report(report)
        if report.has_data and advance:
            self._set_phase("data")
            self.ai_diag.append_dyn(f"已读取 {len(report.faults)} 条故障码 · "
                                    f"{len(report.flows)} 项数据流", cls="done")
        return report

    # ── 诊断分析（三阶段链路） ──────────────────────

    def _start_ai_diagnosis(self, auto: bool = False):
        """auto=True：采集完成后自动触发，用发送时捕获的故障现象；否则取输入框。"""
        if self._running or self._ai_running:
            return
        if not self._out_dir:
            self.ai_diag.show_error("尚未生成报告，请先运行一次 DTS 流程")
            return
        if auto:
            symptom = self._pending_symptom or ""
            notes = self._pending_notes or ""
        else:
            symptom, notes = self.ai_diag.get_input()
            if not symptom:
                self.ai_diag.show_error("请先填写故障现象")
                return
        # 设备名并入 AI 上下文（三阶段链路都可见）
        dev_name = (self._device or {}).get("n", "")
        if dev_name:
            notes = f"车辆类型：{dev_name}\n{notes}" if notes else f"车辆类型：{dev_name}"

        from ai.deepseek import DeepSeekClient
        client = DeepSeekClient()
        if not client.configured:
            if auto:
                # 自动模式未配置 key：软跳过，不打断采集收尾
                self.ai_diag.set_status(
                    "未配置 DeepSeek API Key，自动诊断已跳过；配置后再次运行将自动分析")
                self._dev_status.setText("○ 就绪")
                return
            self.ai_diag.show_error(
                "未配置 DeepSeek API Key（环境变量 DEEPSEEK_API_KEY 或 data/config.json 的 api_key）")
            return

        self._ai_running = True
        report = self._report_loader.load(self._out_dir)
        self.ai_diag.set_report(report)
        self.ai_diag.set_running(True)
        self.ai_diag.set_status("正在确认采集列表…")
        self._dev_status.setText("● 分析中")
        self._set_phase("ai")

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
            _safe_log(logging.ERROR, "诊断分析失败: %s", e)
            self._ai_bridge.ai_failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            _safe_log(logging.ERROR, "诊断分析异常: %s", e)
            self._ai_bridge.ai_failed.emit(f"诊断分析异常：{e}")

    def _on_ai_stage_started(self, no, name):
        self.ai_diag.set_dyn_status(f"正在{name}…")
        self.ai_diag.append_dyn(f"正在{name}…", cls="thinking")

    def _on_ai_stage_done(self, no, name, obj):
        if no == 1:
            self.ai_diag.show_plan(obj.asdict())
            self.ai_diag.set_status("采集计划已生成，正在判断是否需要路试…")
        elif no == 2:
            self.ai_diag.show_locatability(obj.asdict())
            self.ai_diag.set_status("路试判断完成，正在输出维修报告…")
        elif no == 3:
            self.ai_diag.append_dyn("诊断完成，已生成诊断报告。", cls="done")
            self.ai_diag.show_report(obj)
            self.ai_diag.set_status("诊断完成 — 可查看采集计划 / 路试判断 / 维修报告")

    def _on_ai_finished(self, result):
        self._ai_running = False
        self.ai_diag.set_running(False)
        self.ai_diag.set_status("诊断完成 — 可查看采集计划 / 路试判断 / 维修报告")
        self.ai_diag.set_dyn_status("已完成")
        self._dev_status.setText("○ 就绪")
        self._set_phase("report")
        self.shell.toast("AI 诊断已完成")

    def _on_ai_failed(self, msg):
        self._ai_running = False
        self.ai_diag.set_running(False)
        self.ai_diag.show_error(msg)
        self._dev_status.setText("○ 就绪")

    # ── 演示降级：无真机 / 未接入自动化 ─────────────

    def _run_demo_diagnosis(self, note: str):
        """QTimer 依次追加演示动态信息，收尾填充演示报告（不碰真实链路）。"""
        self._ai_running = True
        self.ai_diag.set_running(True)
        self._dev_status.setText("● 分析中")
        self._set_phase("ai")
        total = len(DYN_MSGS)
        for i, msg in enumerate(DYN_MSGS):
            QTimer.singleShot(i * 450, lambda m=msg: self.ai_diag.append_dyn(m["text"], cls=m["cls"]))
            QTimer.singleShot(i * 450, lambda m=msg: self.ai_diag.set_dyn_status(m["text"]))
        QTimer.singleShot(total * 450 + 200, lambda: self._finish_demo(note))

    def _finish_demo(self, note: str):
        rep = build_demo_report()
        self.ai_diag.set_vin(DEMO_VEHICLE)
        self.ai_diag.set_faults(rep.faults)
        self.ai_diag.show_report(build_demo_ai_report())
        self.ai_diag.render_steps(DIAG_STEPS)
        self.ai_diag.set_running(False)
        self.ai_diag.set_status("诊断完成 — 可查看采集计划 / 路试判断 / 维修报告")
        self.ai_diag.set_dyn_status("已完成")
        self._set_phase("report")
        self._ai_running = False
        self._dev_status.setText("○ 就绪")
        self.shell.toast(note)

    # ── 重新诊断 / 导出 ──────────────────────────

    def _on_restart(self):
        """重新诊断：清空结果，回到主页重新选择输入。"""
        self.ai_diag.reset()
        self._set_phase("run")
        self.shell.goPage("home")

    def _export_ai_report(self, result):
        """导出 AI 诊断报告为 Markdown（真实流程 → 输出目录；演示 → reports_dir/DEMO）。"""
        from config.settings import settings
        try:
            out_dir = Path(self._out_dir) if self._out_dir else None
            if out_dir is None:
                out_dir = Path(settings.reports_dir) / "DEMO"
                out_dir.mkdir(parents=True, exist_ok=True)
            lines = ["# AI 智能诊断报告", ""]
            if isinstance(result, dict):
                if result.get("overallConclusion"):
                    lines += ["## 总体结论", str(result["overallConclusion"]), ""]
                for i, d in enumerate(result.get("diagnosisList", []), start=1):
                    lines += [f"## {i}. {d.get('faultPoint', '')}",
                              f"- 可能性：{d.get('probability', '')}"]
                    if d.get("simpleExplanation"):
                        lines += [f"- 说明：{d['simpleExplanation']}"]
                    for g in d.get("guideSteps", []):
                        lines += [f"- {g}"]
                    lines.append("")
            path = out_dir / "ai_report.md"
            path.write_text("\n".join(lines), encoding="utf-8")
            self.shell.toast(f"已导出：{path}")
        except Exception as e:  # noqa: BLE001
            self.shell.toast(f"导出失败：{e}", "crit")
