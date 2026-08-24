"""
页面：
  HomePage  ⌂主页：品牌 logo + 开始诊断（极简入口，面向用户）
  RunPage   ①运行：设备状态 + 取消 + 步骤时间线 + 进度（无日志/无开始按钮）
  DataPage  ②数据：故障码卡片 + 数据流表 + 已保存文件
  AiPage    ③AI 分析：摘要/原因/方案/注意事项（AI 模块接入前为诚实占位）

日志对用户隐藏：操作日志写入 data/logs/ 文件，不在界面展示。
"""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RunPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._running = False
        self._steps = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
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
        tl_scroll = QScrollArea()
        tl_scroll.setWidgetResizable(True)
        tl_scroll.setFrameShape(QFrame.NoFrame)
        tl_widget = QWidget()
        self._timeline = QVBoxLayout(tl_widget)
        self._timeline.setContentsMargins(2, 2, 8, 2)
        self._timeline.setSpacing(2)
        self._timeline.addStretch(1)
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
        self._timeline.addStretch(1)
        self._progress.setValue(done)
        self._step_count_lbl.setText(f"{done} / {len(steps)}")


# ═══════════════════════════════════════════════════════════
#  DataPage  ②数据
# ═══════════════════════════════════════════════════════════

class DataPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DataPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
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
        self._stack_layout.setContentsMargins(24, 18, 24, 18)
        self._stack_layout.setSpacing(10)
        self._stack_layout.addStretch(1)

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
        self._empty.setVisible(not has)
        self._stack.setVisible(has)
        self._status_items.clear()
        if not has:
            return
        self._render_faults(report)
        self._render_flows(report)
        self._render_files(report)
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
#  AiPage  ③AI 分析（AI 模块接入前为诚实占位）
# ═══════════════════════════════════════════════════════════

class AiPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AiPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._report = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(10)

        # 头部：标题 + PRO 徽标 + 说明
        head = QHBoxLayout()
        title = QLabel("AI 分析")
        title.setObjectName("CardTitle")
        head.addWidget(title)
        badge = QLabel("PRO")
        badge.setObjectName("Tier")
        _prop(badge, "grade", "later")
        head.addWidget(badge)
        head.addStretch(1)
        self._sum_lbl = QLabel("等待运行数据")
        self._sum_lbl.setObjectName("SecCount")
        head.addWidget(self._sum_lbl)
        root.addLayout(head)

        # 模块状态提示
        notice = QFrame()
        notice.setObjectName("Notice")
        nv = QVBoxLayout(notice)
        nv.setContentsMargins(14, 12, 14, 12)
        nv.setSpacing(6)
        t = QLabel("AI 分析模块尚未接入（规划中）")
        t.setObjectName("AiHeader")
        nv.addWidget(t)
        d = QLabel("接入后将读取本次采集的故障码与数据流，自动生成故障摘要、"
                   "可能原因推断与分优先级的维修建议。分析仅供辅助判断，不构成维修结论。")
        d.setObjectName("AiText")
        d.setWordWrap(True)
        nv.addWidget(d)
        btn = QPushButton("生成分析 · 开发中")
        btn.setObjectName("Ghost")
        btn.setEnabled(False)
        nv.addWidget(btn)
        root.addWidget(notice)

        # 四块布局（摘要 / 原因 / 方案 / 注意事项），占位状态
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self._block("故障摘要",
            "运行完成后将在此显示故障码汇总与异常数据流概览。"), 0, 0)
        grid.addWidget(self._block("建议修改方案 · 按优先级",
            "按优先级列出维修/排查建议，并标注处理时机（立即 / 下次保养 / 需深入诊断）。"), 0, 1)
        grid.addWidget(self._block("可能原因",
            "结合故障码与数据流推断的可能原因列表。"), 1, 0)
        grid.addWidget(self._block("注意事项",
            "AI 推断的边界说明与实车确认提醒。"), 1, 1)
        root.addLayout(grid)
        root.addStretch(1)

    def _block(self, header, text) -> QFrame:
        card = QFrame()
        card.setObjectName("AiCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        t = QLabel(header)
        t.setObjectName("AiHeader")
        v.addWidget(t)
        d = QLabel(text)
        d.setObjectName("AiText")
        d.setWordWrap(True)
        v.addWidget(d)
        v.addStretch(1)
        return card

    def set_report(self, report: Report | None):
        self._report = report
        if report and report.has_data:
            self._sum_lbl.setText(
                f"基于 {len(report.faults)} 条故障码 + {len(report.flows)} 项数据流")
        else:
            self._sum_lbl.setText("等待运行数据")
