"""
页面：
  HomePage        ⌂主页：品牌 logo + 开始诊断（极简入口，面向用户）
  PhaseBar        流程进度指示（①采集 ②数据 ③AI，纯展示不可点击）
  DiagnosticPage  单页连续诊断流：①采集运行 → ②采集结果(摘要+可展开) → ③AI 诊断
    ├ RunPage  ①采集：设备状态 + 取消 + 步骤时间线 + 进度
    ├ DataPage ②数据：故障码卡片 + 数据流表 + 已保存文件（摘要卡内可展开）
    └ AiPage   ③AI 分析：三段式诊断（采集计划 → 路试判断 → 维修报告）
  RunPage/DataPage/AiPage 均支持 embed=True，作为子部件嵌入单页（去内滚/空态/底部）。

日志对用户隐藏：操作日志写入 data/logs/ 文件，不在界面展示。
"""

import html as _html
import json
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from ui.logo import LogoWidget
from ui.report import Report
from ui.theme import ThemeManager

ICONS = {"done": "✓", "running": "▶", "error": "✗", "cancelled": "■", "pending": "◌"}

VERSION = "v0.1.0"


def _prop(widget, name, value):
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    return widget


def _section_header(text, count="") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    title = QLabel(text)
    title.setObjectName("SecTitle")
    row.addWidget(title)
    row.addStretch(1)
    if count:
        cnt = QLabel(count)
        cnt.setObjectName("SecCount")
        row.addWidget(cnt)
    return row


def _eval_status(value: str, ref: str):
    """按参考范围判断数据流状态 → (status, 文本)。无法判断返回 ("","")"""
    try:
        v = float(str(value).replace(",", "").strip())
    except Exception:
        return "", ""
    ref = (ref or "").strip()
    if not ref:
        return "", ""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", ref)           # 精确值 "0"
    if m:
        if v != float(m.group(1)):
            return "crit", "异常"
        return "ok", "正常"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–—~]\s*(\d+(?:\.\d+)?)", ref)   # 范围 "85 – 105"
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if v < lo:
            return "warn", "偏低"
        if v > hi:
            return "warn", "偏高"
        return "ok", "正常"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[±]\s*(\d+(?:\.\d+)?)", ref)       # 公差 "700 ± 50"
    if m:
        c, d = float(m.group(1)), float(m.group(2))
        if v < c - d:
            return "warn", "偏低"
        if v > c + d:
            return "warn", "偏高"
        return "ok", "正常"
    return "", ""


# ═══════════════════════════════════════════════════════════
#  PhaseBar  单页流程的纯进度指示（不可点击）
# ═══════════════════════════════════════════════════════════

class PhaseBar(QFrame):
    """①采集 → ②数据 → ③AI 的三段进度条，只做状态提示，不承担导航。"""

    _PHASES = [
        ("①", "采集", "DTS 流程"),
        ("②", "数据", "故障码 · 数据流"),
        ("③", "AI 分析", "计划 · 路试 · 报告"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PhaseBar")
        self._dots = []
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(0)
        h.addStretch(1)
        for i, (num, label, sub) in enumerate(self._PHASES):
            if i:
                conn = QLabel("")
                conn.setObjectName("Conn")
                conn.setFixedSize(30, 2)
                h.addWidget(conn)
            dot = QLabel(num)
            dot.setObjectName("StepDot")
            dot.setFixedSize(22, 22)
            dot.setAlignment(Qt.AlignCenter)
            _prop(dot, "stepState", "next")
            h.addWidget(dot)
            v = QVBoxLayout()
            v.setSpacing(0)
            lbl = QLabel(label)
            lbl.setObjectName("StepLabel")
            _prop(lbl, "stepState", "next")
            v.addWidget(lbl)
            sub = QLabel(sub)
            sub.setObjectName("StepSub")
            v.addWidget(sub)
            h.addLayout(v)
            h.addSpacing(8)
            self._dots.append((dot, lbl, sub))
        h.addStretch(1)
        self.set_phase("run")

    def set_phase(self, phase: str):
        """phase ∈ "run" | "data" | "ai"：当前=current、之前=done、之后=next"""
        idx = {"run": 0, "data": 1, "ai": 2}.get(phase, 0)
        for i, (dot, lbl, sub) in enumerate(self._dots):
            state = "current" if i == idx else ("done" if i < idx else "next")
            for w in (dot, lbl, sub):
                _prop(w, "stepState", state)


# ═══════════════════════════════════════════════════════════
#  HomePage  ⌂ 主页（极简入口）
# ═══════════════════════════════════════════════════════════

class HomePage(QWidget):
    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        # 纯 QWidget 需显式声明，样式表背景才会在窗口中绘制
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(0)

        # 品牌 logo（静态完整状态）
        logo = LogoWidget(progress=1.0, size=104)
        logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        root.addWidget(logo, 0, Qt.AlignCenter)
        root.addSpacing(26)

        # 标题：AutoDrive（Auto + 强调 Drive）
        title = QHBoxLayout()
        title.setSpacing(0)
        title.setAlignment(Qt.AlignCenter)
        t1 = QLabel("Auto")
        t1.setObjectName("HomeTitle")
        t2 = QLabel("Drive")
        t2.setObjectName("HomeAcc")
        title.addWidget(t1)
        title.addWidget(t2)
        root.addLayout(title)
        root.addSpacing(8)

        # 副标题
        sub = QLabel("DTS650 诊断数据采集与分析")
        sub.setObjectName("HomeSub")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(34)

        # 开始诊断
        self._start_btn = QPushButton("开始诊断")
        self._start_btn.setObjectName("HomeStart")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.clicked.connect(self.start_requested)
        root.addWidget(self._start_btn, 0, Qt.AlignCenter)
        root.addSpacing(60)

        # 页脚版本
        foot = QLabel(f"AutoDrive {VERSION} · 面向 DTS650 的自动化诊断工具")
        foot.setObjectName("HomeFoot")
        foot.setAlignment(Qt.AlignCenter)
        root.addWidget(foot)

    def set_busy(self, busy: bool):
        """运行期间禁用开始按钮，避免重复触发"""
        self._start_btn.setEnabled(not busy)


# ═══════════════════════════════════════════════════════════
#  RunPage  ①运行
# ═══════════════════════════════════════════════════════════

class RunPage(QWidget):
    cancel_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent=None, embed=False):
        super().__init__(parent)
        self.setObjectName("RunPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._embed = embed
        self._running = False
        self._steps = []
        self._back_btn = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        if self._embed:
            root.setContentsMargins(0, 0, 0, 0)     # 单页模式：外边距由 DiagnosticPage 统一
        else:
            root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        # ── 设备卡片 ──
        root.addLayout(_section_header("设备"))
        card = QFrame()
        card.setObjectName("RunBar")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)
        icon = QLabel("🔧")
        icon.setStyleSheet("font-size: 26px;")
        row.addWidget(icon)
        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel("DTS 诊断仪")
        name.setObjectName("CardTitle")
        desc = QLabel("DTS650 数据流读取 / 故障码诊断")
        desc.setObjectName("DtcDesc")
        info.addWidget(name)
        info.addWidget(desc)
        row.addLayout(info)
        row.addStretch(1)

        self._status_pill = QLabel("就绪")
        self._status_pill.setObjectName("SevBadge")
        row.addWidget(self._status_pill)

        self._cancel_btn = QPushButton("■  取消")
        self._cancel_btn.setObjectName("Danger")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_requested)
        row.addWidget(self._cancel_btn)
        root.addWidget(card)

        # ── 状态 + 进度 ──
        status_row = QHBoxLayout()
        self._status_lbl = QLabel("点击「开始诊断」启动 DTS 流程")
        self._status_lbl.setObjectName("DtcDesc")
        status_row.addWidget(self._status_lbl)
        status_row.addStretch(1)
        self._step_count_lbl = QLabel("0 / 0")
        self._step_count_lbl.setObjectName("SecCount")
        status_row.addWidget(self._step_count_lbl)
        root.addLayout(status_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        root.addWidget(self._progress)

        # ── 步骤时间线 ──
        root.addLayout(_section_header("执行进度"))
        tl_widget = QWidget()
        self._timeline = QVBoxLayout(tl_widget)
        self._timeline.setContentsMargins(2, 2, 8, 2)
        self._timeline.setSpacing(2)
        if not self._embed:
            self._timeline.addStretch(1)
        if self._embed:
            root.addWidget(tl_widget)              # 单页模式：时间线自然展开，无内滚
        else:
            tl_scroll = QScrollArea()
            tl_scroll.setWidgetResizable(True)
            tl_scroll.setFrameShape(QFrame.NoFrame)
            tl_scroll.setWidget(tl_widget)
            root.addWidget(tl_scroll, 1)

            # ── 返回主页（底部） ──
            foot = QHBoxLayout()
            foot.addStretch(1)
            self._back_btn = QPushButton("‹  返回主页")
            self._back_btn.setObjectName("Ghost")
            self._back_btn.clicked.connect(self.back_requested)
            foot.addWidget(self._back_btn)
            root.addLayout(foot)

    # ── 对外接口 ──

    def set_running(self, running: bool):
        self._running = running
        self._cancel_btn.setEnabled(running)
        if self._back_btn is not None:
            self._back_btn.setEnabled(not running)
        if running:
            self._status_pill.setText("执行中")
            _prop(self._status_pill, "grade", "now")
        else:
            self._status_pill.setText("就绪")
            _prop(self._status_pill, "grade", "later")
        if not running:
            self._status_lbl.setText("流程结束 — 可查看数据 / AI 分析")

    def set_status(self, text: str):
        self._status_lbl.setText(text)

    def reset_steps(self, steps):
        self._steps = steps
        self._progress.setRange(0, max(1, len(steps)))
        self._progress.setValue(0)
        self._step_count_lbl.setText(f"0 / {len(steps)}")
        self.render_steps(steps)

    def render_steps(self, steps=None):
        steps = steps if steps is not None else self._steps
        # 重建时间线（步骤事件时调用，量小无需增量更新）
        while self._timeline.count():
            item = self._timeline.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        done = 0
        for idx, step in enumerate(steps, 1):
            st = step.status
            if st == "done":
                done += 1
            row = QFrame()
            row.setObjectName("StepRow")
            _prop(row, "st", st)
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 4, 8, 4)
            h.setSpacing(10)
            icon = QLabel(ICONS.get(st, "◌"))
            icon.setObjectName("StepIcon")
            icon.setFixedSize(18, 18)
            icon.setAlignment(Qt.AlignCenter)
            _prop(icon, "st", st)
            h.addWidget(icon)
            name = QLabel(f"{idx}.  {step.name}")
            name.setObjectName("StepName")
            _prop(name, "st", st)
            h.addWidget(name)
            h.addStretch(1)
            note = QLabel("")
            note.setObjectName("StepNote")
            if st == "error" and step.error:
                note.setText(step.error[:60])
            elif st == "running":
                note.setText(f"第 {step.attempt}/{step.retry} 次")
            if note.text():
                h.addWidget(note)
            self._timeline.addWidget(row)
        if not self._embed:
            self._timeline.addStretch(1)
        self._progress.setValue(done)
        self._step_count_lbl.setText(f"{done} / {len(steps)}")


# ═══════════════════════════════════════════════════════════
#  DataPage  ②数据
# ═══════════════════════════════════════════════════════════

class DataPage(QWidget):
    def __init__(self, parent=None, embed=False):
        super().__init__(parent)
        self.setObjectName("DataPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._embed = embed
        self._report = None
        self._status_items = []   # [(item, status)] 用于主题切换时重上色
        self._build_ui()
        tm = ThemeManager.instance()
        if tm is not None:
            tm.changed.connect(self._on_theme_changed)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        if self._embed:
            self._stack_layout.setContentsMargins(0, 0, 0, 0)
        else:
            self._stack_layout.setContentsMargins(24, 18, 24, 18)
        self._stack_layout.setSpacing(10)
        if not self._embed:
            self._stack_layout.addStretch(1)

        if self._embed:
            root.addWidget(self._stack)            # 单页模式：内容直接嵌入，无内滚/空态
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(self._stack)
            root.addWidget(scroll)

            # 空状态
            self._empty = QLabel("尚未生成报告 — 先运行一次 DTS 流程")
            self._empty.setObjectName("DtcDesc")
            self._empty.setAlignment(Qt.AlignCenter)
            root.addWidget(self._empty)

        self.set_report(None)

    def set_report(self, report: Report | None):
        self._report = report
        has = report is not None and report.has_data
        if not self._embed:
            self._empty.setVisible(not has)
        self._stack.setVisible(has)
        self._status_items.clear()
        if not has:
            return
        self._render_faults(report)
        self._render_flows(report)
        self._render_files(report)
        if not self._embed:
            self._stack_layout.addStretch(1)

    def _clear_stack(self):
        while self._stack_layout.count():
            item = self._stack_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_faults(self, report: Report):
        self._clear_stack()
        self._stack_layout.addLayout(_section_header(
            "故障码", f"{len(report.faults)} 条 · "
            f"{sum(1 for f in report.faults if f.severity == 'crit')} 严重"))
        if report.faults:
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            for i, f in enumerate(report.faults):
                grid.addWidget(self._make_dtc_card(f), i // 3, i % 3)
            self._stack_layout.addLayout(grid)
        else:
            self._stack_layout.addWidget(self._note_label("本次未采集到故障码"))

    def _make_dtc_card(self, fault) -> QFrame:
        card = QFrame()
        card.setObjectName("DtcCard")
        _prop(card, "sev", fault.severity)
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(4)
        top = QHBoxLayout()
        code = QLabel(fault.code)
        code.setObjectName("DtcCode")
        top.addWidget(code)
        top.addStretch(1)
        badge = QLabel("严重" if fault.severity == "crit" else "一般")
        badge.setObjectName("SevBadge")
        top.addWidget(badge)
        v.addLayout(top)
        name = QLabel(fault.desc or "—")
        name.setObjectName("DtcName")
        name.setWordWrap(True)
        v.addWidget(name)
        return card

    def _render_flows(self, report: Report):
        self._stack_layout.addSpacing(10)
        self._stack_layout.addLayout(_section_header(
            "数据流", f"{len(report.flows)} 项"))
        if not report.flows:
            self._stack_layout.addWidget(self._note_label("本次未采集到数据流"))
            return
        card = QFrame()
        card.setObjectName("FlowCard")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.setContentsMargins(14, 10, 14, 10)
        t = QLabel("数据流采样")
        t.setObjectName("CardTitle")
        head.addWidget(t)
        head.addStretch(1)
        cnt = QLabel("参考范围来自 DTS 导出")
        cnt.setObjectName("SecCount")
        head.addWidget(cnt)
        cv.addLayout(head)
        table = QTableWidget(len(report.flows), 5)
        table.setObjectName("FlowTable")
        table.setHorizontalHeaderLabels(["参数", "实时值", "单位", "参考范围", "状态"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        for r, item in enumerate(report.flows):
            status, text = _eval_status(item.value, item.ref)
            cells = [item.name, item.value, item.unit, item.ref,
                     f"● {text}" if text else "—"]
            for c, val in enumerate(cells):
                cell = QTableWidgetItem(val)
                if c == 4 and text:
                    cell.setForeground(QColor(toks.get(
                        {"ok": "ok", "warn": "warn", "crit": "crit"}.get(status, "dim"),
                        "#888888")))
                    self._status_items.append((cell, status))
                table.setItem(r, c, cell)
        cv.addWidget(table)
        self._stack_layout.addWidget(card)

    def _render_files(self, report: Report):
        self._stack_layout.addSpacing(10)
        self._stack_layout.addLayout(_section_header(
            "已保存文件", f"{len(report.files)} 个"))
        row = QHBoxLayout()
        row.setSpacing(8)
        for f in report.files[:12]:
            size = f"{f.size/1024:.1f} KB" if f.size >= 1024 else f"{f.size} B"
            chip = QLabel(f"✓ {f.name} · {size}")
            chip.setObjectName("FileChip")
            row.addWidget(chip)
        row.addStretch(1)
        self._stack_layout.addLayout(row)

    def _note_label(self, text) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("DtcDesc")
        return lbl

    def _on_theme_changed(self, _resolved):
        if not self._report:
            return
        tm = ThemeManager.instance()
        if tm is None:
            return
        toks = tm.tokens
        key = {"ok": "ok", "warn": "warn", "crit": "crit"}.get
        for item, status in self._status_items:
            item.setForeground(QColor(toks.get(key(status, "dim"), "#888888")))


# ═══════════════════════════════════════════════════════════
#  AiPage  ③AI 分析：三段式诊断（采集计划 → 路试判断 → 维修报告）
# ═══════════════════════════════════════════════════════════

_STAGES = {
    1: ("确认采集列表", "AI 选择数据流与采集工况"),
    2: ("是否需要路试", "判断原地数据能否定位"),
    3: ("输出维修报告", "生成排查方案"),
}


def _rich(text) -> str:
    """转义模型文本，仅放行 <b>/<strong>/<br> 标签（QTextBrowser 可渲染）"""
    esc = _html.escape(str(text))
    for tag in ("br", "br/", "br /"):
        esc = esc.replace(f"&lt;{tag}&gt;", "<br>")
    esc = esc.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    esc = esc.replace("&lt;strong&gt;", "<b>").replace("&lt;/strong&gt;", "</b>")
    esc = esc.replace("\r\n", "\n").replace("\n", "<br>")
    return esc


class AiPage(QWidget):
    """③AI 分析：故障现象输入 → 三段式诊断链路 → 结果卡片"""

    start_requested = Signal()   # 用户点「开始 AI 诊断」→ wizard 起后台线程
    stop_requested = Signal()

    def __init__(self, parent=None, embed=False):
        super().__init__(parent)
        self.setObjectName("AiPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._embed = embed
        self._report = None
        self._out_dir = None
        self._running = False
        self._stage_rows = {}     # no -> (row, icon, name, note)
        self._build_ui()

    # ── 构建 UI ──────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        if self._embed:
            self._stack_layout.setContentsMargins(0, 0, 0, 0)
        else:
            self._stack_layout.setContentsMargins(24, 18, 24, 18)
        self._stack_layout.setSpacing(10)
        if not self._embed:
            self._stack_layout.addStretch(1)

        if self._embed:
            root.addWidget(self._stack)            # 单页模式：内容直接嵌入，无内滚
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(self._stack)
            root.addWidget(scroll)

        # ── 头部 ──
        self._stack_layout.insertLayout(0, self._header_row())
        self._stack_layout.insertWidget(1, self._input_card())
        self._stack_layout.insertLayout(2, _section_header("诊断链路"))
        self._stack_layout.insertWidget(3, self._stage_timeline())
        self._stack_layout.insertWidget(4, self._plan_card())
        self._stack_layout.insertWidget(5, self._loc_card())
        self._stack_layout.insertWidget(6, self._report_card())

        # ── 页脚说明 ──
        self._stack_layout.insertLayout(7, self._footer_row())

    def _header_row(self) -> QHBoxLayout:
        head = QHBoxLayout()
        title = QLabel("③ AI 诊断")
        title.setObjectName("SecTitle")
        title.setStyleSheet("font-size: 15px;")
        head.addWidget(title)

        # 模型 chip
        try:
            from config.settings import settings
            model = getattr(settings, "ai_model", "deepseek-chat")
        except Exception:
            model = "deepseek-chat"
        chip = QLabel(f"DeepSeek · {model}")
        chip.setObjectName("Chip")
        head.addWidget(chip)
        head.addStretch(1)
        self._sum_lbl = QLabel("等待运行数据")
        self._sum_lbl.setObjectName("SecCount")
        head.addWidget(self._sum_lbl)
        return head

    def _input_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("AiCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)

        lbl = QLabel("故障现象")
        lbl.setObjectName("AiHeader")
        v.addWidget(lbl)
        self._symptom_input = QPlainTextEdit()
        self._symptom_input.setObjectName("AiInput")
        self._symptom_input.setPlaceholderText(
            "可留空：将自动依据故障码与数据流分析\n例：动力不足、发动机抖动、故障灯亮…")
        self._symptom_input.setFixedHeight(64)
        v.addWidget(self._symptom_input)

        lbl2 = QLabel("补充说明（可选）")
        lbl2.setObjectName("AiHeader")
        v.addWidget(lbl2)
        self._notes_input = QPlainTextEdit()
        self._notes_input.setObjectName("AiInput")
        self._notes_input.setPlaceholderText(
            "例：已做过的维修、车辆配置、未安装的部件、特殊工况等。")
        self._notes_input.setFixedHeight(40)
        v.addWidget(self._notes_input)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._run_btn = QPushButton("开始 AI 诊断")
        self._run_btn.setObjectName("Primary")
        self._run_btn.setCursor(Qt.PointingHandCursor)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self.start_requested)
        row.addWidget(self._run_btn)
        self._status_lbl = QLabel("先运行一次 DTS 流程，即可开始 AI 诊断")
        self._status_lbl.setObjectName("DtcDesc")
        row.addWidget(self._status_lbl)
        row.addStretch(1)
        v.addLayout(row)
        return card

    def _stage_timeline(self) -> QFrame:
        wrap = QFrame()
        wrap.setObjectName("AiCard")
        wv = QVBoxLayout(wrap)
        wv.setContentsMargins(10, 10, 10, 10)
        wv.setSpacing(2)
        for no, (name, sub) in _STAGES.items():
            row, icon, name_lbl, note = self._make_stage_row(no, name, sub)
            self._stage_rows[no] = (row, icon, name_lbl, note)
            wv.addWidget(row)
        return wrap

    def _make_stage_row(self, no, name, sub):
        row = QFrame()
        row.setObjectName("StepRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 5, 8, 5)
        h.setSpacing(10)
        icon = QLabel(ICONS.get("pending", "◌"))
        icon.setObjectName("StepIcon")
        icon.setFixedSize(18, 18)
        icon.setAlignment(Qt.AlignCenter)
        _prop(icon, "st", "pending")
        h.addWidget(icon)
        txt = QVBoxLayout()
        txt.setSpacing(0)
        name_lbl = QLabel(f"{no}.  {name}")
        name_lbl.setObjectName("StepName")
        _prop(name_lbl, "st", "pending")
        txt.addWidget(name_lbl)
        sub_lbl = QLabel(sub)
        sub_lbl.setObjectName("AiStageSub")
        txt.addWidget(sub_lbl)
        h.addLayout(txt)
        h.addStretch(1)
        note = QLabel("")
        note.setObjectName("StepNote")
        _prop(note, "st", "pending")
        h.addWidget(note)
        _prop(row, "st", "pending")
        return row, icon, name_lbl, note

    def _plan_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("AiCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)
        t = QLabel("① 采集计划")
        t.setObjectName("AiHeader")
        v.addWidget(t)
        self._plan_chips = QHBoxLayout()
        self._plan_chips.setSpacing(6)
        self._plan_chips.addStretch(1)
        v.addLayout(self._plan_chips)
        self._plan_cond = QLabel("")
        self._plan_cond.setObjectName("DtcDesc")
        self._plan_cond.setWordWrap(True)
        v.addWidget(self._plan_cond)
        card.setVisible(False)
        return card

    def _loc_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("AiCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)
        t = QLabel("② 路试判断")
        t.setObjectName("AiHeader")
        v.addWidget(t)
        row = QHBoxLayout()
        row.setSpacing(8)
        self._loc_verdict = QLabel("")
        self._loc_verdict.setObjectName("AiVerdict")
        row.addWidget(self._loc_verdict)
        self._loc_reason = QLabel("")
        self._loc_reason.setObjectName("DtcDesc")
        self._loc_reason.setWordWrap(True)
        row.addWidget(self._loc_reason, 1)
        v.addLayout(row)
        card.setVisible(False)
        return card

    def _report_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("AiCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)
        t = QLabel("③ 维修报告")
        t.setObjectName("AiHeader")
        v.addWidget(t)
        self._report_browser = QTextBrowser()
        self._report_browser.setObjectName("AiReport")
        self._report_browser.setOpenExternalLinks(False)
        self._report_browser.setMinimumHeight(220)
        v.addWidget(self._report_browser)
        card.setVisible(False)
        return card

    def _footer_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        note = QLabel("分析基于本次采集的故障码与数据流 · AI 结果仅供辅助判断，不构成维修结论")
        note.setObjectName("DtcDesc")
        row.addWidget(note)
        return row

    # ── 对外接口 ──────────────────────────────────────

    def get_input(self):
        """返回 (故障现象, 补充说明)"""
        return (self._symptom_input.toPlainText().strip(),
                self._notes_input.toPlainText().strip())

    def set_report(self, report: Report | None):
        self._report = report
        has = report is not None and report.has_data
        self._run_btn.setEnabled(has and not self._running)
        if has:
            self._sum_lbl.setText(
                f"基于 {len(report.faults)} 条故障码 + {len(report.flows)} 项数据流")
            self._status_lbl.setText("采集完成后将自动开始分析，也可手动填写现象后开始")
            out_dir = getattr(report, "out_dir", None)
            if out_dir and not self._running:
                self.load_from(out_dir)
        else:
            self._sum_lbl.setText("等待运行数据")
            self._status_lbl.setText("先运行一次 DTS 流程，即可开始 AI 诊断")

    def load_from(self, out_dir):
        """报告重新加载/切换时，从 out_dir 恢复已保存的 AI 结果（重跑后回看不丢）"""
        self._out_dir = Path(out_dir)
        plan_p = self._out_dir / "ai_collection_plan.json"
        loc_p = self._out_dir / "ai_locatability.json"
        rep_p = self._out_dir / "ai_report.json"
        try:
            if plan_p.exists():
                self.show_plan(json.loads(plan_p.read_text(encoding="utf-8")))
                self._set_stage(1, "done", "已完成")
            if loc_p.exists():
                self.show_locatability(json.loads(loc_p.read_text(encoding="utf-8")))
                self._set_stage(2, "done", "已完成")
            if rep_p.exists():
                self.show_report(json.loads(rep_p.read_text(encoding="utf-8")))
                self._set_stage(3, "done", "已完成")
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("autodrive.ui.pages").warning("AI 结果恢复失败: %s", e)

    def reset(self):
        """开始新一轮诊断：清空结果、状态归位"""
        self._running = False
        self._run_btn.setEnabled(self._report is not None and self._report.has_data)
        self._run_btn.setText("开始 AI 诊断")
        self._status_lbl.setText("诊断进行中…")
        self._plan_card_ref().setVisible(False)
        self._loc_card_ref().setVisible(False)
        self._report_card_ref().setVisible(False)
        for no in _STAGES:
            self._set_stage(no, "pending", "")

    def set_running(self, running: bool):
        self._running = running
        self._run_btn.setEnabled(not running and self._report is not None
                                 and self._report.has_data)
        self._run_btn.setText("诊断中…" if running else "开始 AI 诊断")

    def set_status(self, text: str):
        self._status_lbl.setText(text)

    def _set_stage(self, no: int, state: str, note: str = ""):
        row, icon, name_lbl, note_lbl = self._stage_rows.get(no, (None,) * 4)
        if row is None:
            return
        icon.setText(ICONS.get(state, "◌"))
        note_lbl.setText(note if note else "")
        for w in (row, icon, name_lbl, note_lbl):
            _prop(w, "st", state)

    def set_stage(self, no: int, state: str, note: str = ""):
        self._set_stage(no, state, note)

    def show_plan(self, data: dict):
        """渲染采集计划：推荐数据流 chips + 工况"""
        card = self._plan_card_ref()
        card.setVisible(True)
        # 清空旧的 chips（保留 stretch）
        while self._plan_chips.count() > 1:
            item = self._plan_chips.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        streams = data.get("streams") or []
        if streams:
            for s in streams[:30]:
                chip = QLabel(s)
                chip.setObjectName("Chip")
                self._plan_chips.insertWidget(self._plan_chips.count() - 1, chip)
        else:
            note = QLabel("AI 未返回推荐数据流")
            note.setObjectName("DtcDesc")
            self._plan_chips.insertWidget(self._plan_chips.count() - 1, note)
        cond = (data.get("working_conditions") or "").strip()
        self._plan_cond.setText(f"采集工况：{cond}" if cond else "采集工况：—")

    def show_locatability(self, data: dict):
        card = self._loc_card_ref()
        card.setVisible(True)
        locatable = bool(data.get("is_locatable"))
        self._loc_verdict.setText("可原地定位 · 无需路试" if locatable else "需路试 / 复测")
        _prop(self._loc_verdict, "verdict",
              "locatable" if locatable else "roadtest")
        self._loc_reason.setText(str(data.get("reason") or ""))

    def show_report(self, data: dict):
        card = self._report_card_ref()
        card.setVisible(True)
        self._report_browser.setHtml(self._build_report_html(data))

    def show_error(self, msg: str):
        self._status_lbl.setText(f"诊断失败：{msg}")
        # 正在运行的阶段标红
        for no in _STAGES:
            row, icon, name_lbl, note_lbl = self._stage_rows[no]
            if icon.text() == ICONS.get("running"):
                self._set_stage(no, "error", "失败")
        self._run_btn.setText("重试")

    # ── 私有：卡片引用 + 报告 HTML ─────────────────────

    def _plan_card_ref(self):
        return self._stack_layout.itemAt(4).widget()

    def _loc_card_ref(self):
        return self._stack_layout.itemAt(5).widget()

    def _report_card_ref(self):
        return self._stack_layout.itemAt(6).widget()

    def _build_report_html(self, data: dict) -> str:
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        acc = toks.get("acc", "#0D9488")
        tx = toks.get("tx", "#17213A")
        mut = toks.get("mut", "#5C6B82")
        warn = toks.get("warn", "#B45309")
        panel = toks.get("panel", "#F7F9FC")

        parts = ["<html><body style='margin:0;'>"]
        concl = (data.get("overallConclusion") or "").strip()
        if concl:
            parts.append(
                f"<div style='font-size:14px; font-weight:600; color:{acc};"
                f" line-height:1.8; margin-bottom:12px;'>{_rich(concl)}</div>")
        diags = data.get("diagnosisList") or []
        if not diags:
            parts.append(f"<div style='color:{mut};'>（AI 未返回具体排查条目）</div>")
        for i, d in enumerate(diags, 1):
            fp = (d.get("faultPoint") or "—").strip()
            prob = (d.get("probability") or "").strip()
            expl = (d.get("simpleExplanation") or "").strip()
            steps = d.get("guideSteps") or []
            parts.append(
                f"<div style='margin-bottom:12px; padding:10px 12px;"
                f" background:{panel}; border-radius:8px;'>")
            parts.append(
                f"<div style='font-size:13px; font-weight:700; color:{tx};'>"
                f"核心病灶 {i} · {_rich(fp)}</div>")
            if prob:
                parts.append(
                    f"<div style='font-size:11px; color:{warn};"
                    f" margin:2px 0 6px 0;'>{_rich(prob)}</div>")
            if expl:
                parts.append(
                    f"<div style='font-size:13px; color:{tx}; line-height:1.8;"
                    f" margin-bottom:6px;'>诊断逻辑：{_rich(expl)}</div>")
            if steps:
                parts.append(
                    f"<div style='font-size:12px; font-weight:600; color:{mut};"
                    f" margin-top:6px;'>排查处方</div>")
                for j, s in enumerate(steps, 1):
                    s = (s or "").strip()
                    if not s:
                        continue
                    parts.append(
                        f"<div style='font-size:13px; color:{tx}; line-height:1.9;"
                        f" margin-top:4px;'><b>{j}.</b> {_rich(s)}</div>")
            parts.append("</div>")
        parts.append("</body></html>")
        return "".join(parts)


# ═══════════════════════════════════════════════════════════
#  DiagnosticPage  单页连续诊断流（去掉分页切换）
#  ①采集运行 → ②采集结果(紧凑摘要+可展开) → ③AI 诊断，随流程推进自动展开。
# ═══════════════════════════════════════════════════════════

class DiagnosticPage(QWidget):
    """单页连续诊断流：三个既有页面类以 embed=True 组合进一个滚动区。"""

    start_requested = Signal()    # 内嵌 AiPage 转发（开始 AI 诊断）
    cancel_requested = Signal()   # 内嵌 RunPage 转发（取消 DTS）
    back_requested = Signal()     # 底部「返回主页」

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DiagnosticPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._report = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setObjectName("DiagnosticPage")
        content.setAttribute(Qt.WA_StyledBackground, True)
        self._content = QVBoxLayout(content)
        self._content.setContentsMargins(24, 18, 24, 18)
        self._content.setSpacing(14)

        # ── ① 采集运行（始终可见） ──
        self._content.addLayout(_section_header("① 采集运行"))
        self.run = RunPage(embed=True)
        self.run.cancel_requested.connect(self.cancel_requested)
        self._content.addWidget(self.run)

        # ── ② 采集结果（初始隐藏；紧凑摘要 + 可展开明细） ──
        self._data_section = QFrame()
        self._data_section.setObjectName("AiCard")
        dv = QVBoxLayout(self._data_section)
        dv.setContentsMargins(16, 14, 16, 14)
        dv.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(10)
        title = QLabel("② 采集结果")
        title.setObjectName("AiHeader")
        head.addWidget(title)
        self._sum_chips = QHBoxLayout()
        self._sum_chips.setSpacing(6)
        head.addLayout(self._sum_chips)
        head.addStretch(1)
        self._toggle_btn = QPushButton("▸ 展开明细")
        self._toggle_btn.setObjectName("Ghost")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_detail)
        head.addWidget(self._toggle_btn)
        dv.addLayout(head)
        self.data = DataPage(embed=True)
        self.data.setVisible(False)
        dv.addWidget(self.data)
        self._data_section.setVisible(False)
        self._content.addWidget(self._data_section)

        # ── ③ AI 诊断（有数据后启用） ──
        self.ai = AiPage(embed=True)
        self.ai.start_requested.connect(self.start_requested)
        self.ai.setVisible(False)
        self._content.addWidget(self.ai)

        # ── 底部返回 ──
        foot = QHBoxLayout()
        foot.addStretch(1)
        self._back_btn = QPushButton("‹  返回主页")
        self._back_btn.setObjectName("Ghost")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_requested)
        foot.addWidget(self._back_btn)
        self._content.addLayout(foot)

        self._scroll.setWidget(content)
        root.addWidget(self._scroll)

    # ── 对外接口 ──────────────────────────────────────

    def set_report(self, report: Report | None):
        """报告就绪：渲染数据明细 + AI 恢复，按 has_data 显示②③节"""
        self._report = report
        has = report is not None and report.has_data
        self.data.set_report(report)
        self.ai.set_report(report)
        self._data_section.setVisible(has)
        self.ai.setVisible(has)
        if has:
            self._rebuild_summary(report)

    def _rebuild_summary(self, report: Report):
        while self._sum_chips.count():
            item = self._sum_chips.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for text in (f"{len(report.faults)} 条故障码",
                     f"{len(report.flows)} 项数据流",
                     f"{len(report.files)} 个文件"):
            chip = QLabel(text)
            chip.setObjectName("Chip")
            self._sum_chips.addWidget(chip)

    def _toggle_detail(self):
        on = self.data.isHidden()          # 收起态点击 → 展开（用 isHidden 判断显式状态）
        self.data.setVisible(on)
        self._toggle_btn.setText("▾ 收起明细" if on else "▸ 展开明细")
        self.scroll_to(self.data if on else self._data_section)

    def reset_all(self):
        """新一次 DTS 前调用：收起②③节、清空 AI 结果"""
        self._data_section.setVisible(False)
        self.ai.setVisible(False)
        self.data.setVisible(False)
        self._toggle_btn.setText("▸ 展开明细")
        self.ai.reset()

    def scroll_to(self, widget):
        """延迟到布局稳定后把 widget 滚入可视区（自动跟随当前阶段）"""
        QTimer.singleShot(0, lambda: self._scroll.ensureWidgetVisible(widget, 60, 60))
