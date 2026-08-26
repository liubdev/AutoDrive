"""
页面：
  ShieldMark     方案 E 顶栏蓝盾标（QPainter 绘制，免 SVG 资源）
  GlyphButton    圆形图标按钮（history / settings，QPainter 绘制）
  HomePage        主页·设备选择（ct1）：车型卡片 → 进入分析页
  VehicleGlyph   车型迷你图标（轿车/SUV/卡车/新能源，QPainter 绘制）
  PhaseBar        ct2 四节点步进器（①选择车型 ②描述问题 ③AI分析中 ④诊断报告）
  DiagnosticPage  分析页：面包屑 + 步进器 + 单页连续诊断流（①采集运行→②采集结果→③诊断分析）
    ├ RunPage  ①采集：设备状态 + 取消 + 步骤时间线 + 进度
    ├ DataPage ②数据：故障码卡片 + 数据流表 + 已保存文件（摘要卡内可展开）
    └ AiPage   ③诊断分析：问题输入条 + 三段式诊断链路 + 维修报告（结果 widget 渲染）
  RunPage/DataPage/AiPage 均支持 embed=True，作为子部件嵌入单页（去内滚/空态/底部）。

日志对用户隐藏：操作日志写入 data/logs/ 文件，不在界面展示。
"""

import html as _html
import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ui.report import Report
from ui.theme import ThemeManager

ICONS = {"done": "✓", "running": "▶", "error": "✗", "cancelled": "■", "pending": "◌"}

VERSION = "v1.0.0"


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
#  PhaseBar  ct2 四节点步进器（①选择车型 ②描述问题 ③AI分析中 ④诊断报告）
# ═══════════════════════════════════════════════════════════

class PhaseBar(QFrame):
    """ct2 消费级四节点步进器：done=绿✓ current=蓝● next=灰序号，只做状态提示。"""

    _PHASES = [
        ("①", "选择车型", "已选择"),
        ("②", "描述问题", "自动识别或手动输入"),
        ("③", "AI 分析中", "采集数据 + AI 分析"),
        ("④", "诊断报告", "生成排查建议"),
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
        """phase ∈ "run" | "data" | "ai" | "report"（4 节点步进）：
        done=✓ current=● next=序号。
          run     → ①✓ ②● ③ ④          （选择车型完成，等待描述问题）
          data/ai → ①✓ ②✓ ③● ④         （采集 + AI 分析中）
          report  → ①✓ ②✓ ③✓ ④●        （报告就绪）"""
        idx = {"run": 1, "data": 2, "ai": 2, "report": 3}.get(phase, 1)
        for i, (dot, lbl, sub) in enumerate(self._dots):
            if i < idx:
                state, text = "done", "✓"
            elif i == idx:
                state, text = "current", "●"
            else:
                state, text = "next", self._PHASES[i][0]
            dot.setText(text)
            for w in (dot, lbl, sub):
                _prop(w, "stepState", state)


# ═══════════════════════════════════════════════════════════
#  ShieldMark  方案 E 顶栏蓝盾标（QPainter 绘制，免 SVG 资源）
#  GlyphButton 圆形图标按钮（history / settings）
# ═══════════════════════════════════════════════════════════

class ShieldMark(QWidget):
    """蓝色圆角方块 + 白描边盾 + 打勾，读取主题强调色实时绘制。"""

    def __init__(self, size: int = 28, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        acc = QColor(toks.get("acc", "#3880F0"))
        ink = QColor(toks.get("acc_ink", "#FFFFFF"))
        s = float(self.width())
        m = max(2.0, s * 0.06)
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), s * 0.24, s * 0.24)
        # 盾形：五边形轮廓（白描边）
        cx = s / 2.0
        w = s * 0.46                       # 盾宽
        h = s * 0.52                       # 盾高
        top = s * 0.16
        path = QPainterPath()
        path.moveTo(cx - w / 2, top)
        path.lineTo(cx - w / 2, top + h * 0.55)
        path.lineTo(cx, top + h)           # 底部尖角
        path.lineTo(cx + w / 2, top + h * 0.55)
        path.lineTo(cx + w / 2, top)
        path.closeSubpath()
        pen = QPen(ink, max(1.5, s * 0.07))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # 打勾
        p.drawLine(QPointF(cx - w * 0.16, top + h * 0.55),
                   QPointF(cx - w * 0.02, top + h * 0.72))
        p.drawLine(QPointF(cx - w * 0.02, top + h * 0.72),
                   QPointF(cx + w * 0.22, top + h * 0.32))


class GlyphButton(QPushButton):
    """圆形图标按钮：painter 绘制 history（时钟回旋）/ settings（齿轮），悬停描边变蓝。"""

    def __init__(self, glyph: str, parent=None, tooltip: str = ""):
        super().__init__(parent)
        self._glyph = glyph
        self.setFixedSize(38, 38)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        line = QColor(toks.get("line", "#E5E9F0"))
        mut = QColor(toks.get("mut", "#5B6573"))
        acc = QColor(toks.get("acc", "#3880F0"))
        acc_soft = QColor(toks.get("acc_soft", "#EAF1FD"))
        hover = self.underMouse()
        fg = acc if hover else mut
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        p.setPen(QPen(acc if hover else line, 1.5))
        p.setBrush(acc_soft if hover else Qt.NoBrush)
        p.drawEllipse(r)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        if self._glyph == "history":
            pen = QPen(fg, 1.7)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            # 时钟：圆 + 分针 + 时针
            p.drawEllipse(QPointF(cx, cy + 1.0), 8.0, 8.0)
            p.drawLine(QPointF(cx, cy + 1.0), QPointF(cx, cy - 2.5))
            p.drawLine(QPointF(cx, cy + 1.0), QPointF(cx + 4.0, cy + 2.0))
            # 回旋箭头（左上弧）
            p.drawArc(QRectF(cx - 9.0, cy - 9.0, 18.0, 18.0), 160 * 16, -120 * 16)
            ax, ay = cx - 9.4, cy - 7.6
            p.drawLine(QPointF(ax, ay), QPointF(ax - 1.0, ay - 3.2))
            p.drawLine(QPointF(ax, ay), QPointF(ax + 2.2, ay - 2.0))
        else:  # settings 齿轮：粗虚线圆 + 细实线圆 + 中心孔
            p.setPen(QPen(fg, 2.4))
            p.setBrush(Qt.NoBrush)
            pen2 = QPen(fg, 2.4)
            pen2.setCapStyle(Qt.RoundCap)
            pen2.setDashPattern([2.2, 3.0])
            p.setPen(pen2)
            p.drawEllipse(QRectF(cx - 9.0, cy - 9.0, 18.0, 18.0))
            p.setPen(QPen(fg, 1.6))
            p.drawEllipse(QRectF(cx - 4.0, cy - 4.0, 8.0, 8.0))


# ═══════════════════════════════════════════════════════════
#  主页·设备选择（ct1）：
#    VehicleGlyph 车型迷你图标 / SparkIcon ✦ / ClipIcon 回形针
#    SendButton 圆形发送 / DeviceCard 车型卡 / HomePage 主页
# ═══════════════════════════════════════════════════════════

class VehicleGlyph(QWidget):
    """QPainter 车型迷你图标：car / suv / truck / ev（描边线稿，跟随强调色）"""

    def __init__(self, kind: str, size: int = 46, parent=None):
        super().__init__(parent)
        self._kind = kind
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        acc = QColor(toks.get("acc", "#3880F0"))
        s = float(self.width())
        c = s / 2.0
        pen = QPen(acc, max(1.6, s * 0.055))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        kind = self._kind
        if kind == "suv":
            p.drawRoundedRect(QRectF(c - s * 0.36, c - s * 0.04, s * 0.72, s * 0.22), s * 0.05, s * 0.05)
            p.drawRoundedRect(QRectF(c - s * 0.26, c - s * 0.40, s * 0.52, s * 0.36), s * 0.05, s * 0.05)
        elif kind == "truck":
            p.drawRoundedRect(QRectF(c - s * 0.42, c - s * 0.10, s * 0.30, s * 0.26), s * 0.05, s * 0.05)
            p.drawRoundedRect(QRectF(c - s * 0.04, c - s * 0.26, s * 0.46, s * 0.42), s * 0.05, s * 0.05)
        else:  # car / ev 共用轿车身
            p.drawRoundedRect(QRectF(c - s * 0.36, c - s * 0.12, s * 0.72, s * 0.26), s * 0.06, s * 0.06)
            p.drawRoundedRect(QRectF(c - s * 0.22, c - s * 0.36, s * 0.44, s * 0.24), s * 0.06, s * 0.06)
        # 车轮
        for wx in (-1, 1):
            p.drawEllipse(QPointF(c + wx * s * 0.27, c + s * 0.20), s * 0.07, s * 0.07)
        if kind == "ev":
            # 闪电
            bolt = QPainterPath()
            bx = c + s * 0.02
            bolt.moveTo(bx - s * 0.08, c - s * 0.30)
            bolt.lineTo(bx + s * 0.10, c - s * 0.02)
            bolt.lineTo(bx + s * 0.02, c - s * 0.02)
            bolt.lineTo(bx + s * 0.10, c + s * 0.22)
            bolt.lineTo(bx - s * 0.12, c - s * 0.04)
            bolt.lineTo(bx - s * 0.02, c - s * 0.04)
            bolt.closeSubpath()
            p.drawPath(bolt)


class SparkIcon(QWidget):
    """四角星 ✦：输入条前缀图标"""

    def __init__(self, size: int = 18, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        mut = QColor(toks.get("mut", "#5B6573"))
        c = self.width() / 2.0
        s = self.width() / 2.0 - 2
        path = QPainterPath()
        path.moveTo(c, c - s)
        path.lineTo(c + s * 0.16, c - s * 0.16)
        path.lineTo(c + s, c)
        path.lineTo(c + s * 0.16, c + s * 0.16)
        path.lineTo(c, c + s)
        path.lineTo(c - s * 0.16, c + s * 0.16)
        path.lineTo(c - s, c)
        path.lineTo(c - s * 0.16, c - s * 0.16)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(mut)
        p.drawPath(path)


class ClipIcon(QWidget):
    """回形针：输入条装饰图标"""

    def __init__(self, size: int = 18, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        dim = QColor(toks.get("dim", "#98A2B0"))
        c = self.width() / 2.0
        s = self.width() / 2.0 - 2
        pen = QPen(dim, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(c - s * 0.45, c + s * 0.30)
        path.lineTo(c - s * 0.45, c - s * 0.25)
        path.arcTo(QRectF(c - s * 0.45, c - s * 0.35, s * 0.60, s * 0.60), 180, -180)
        path.lineTo(c + s * 0.30, c + s * 0.05)
        p.drawPath(path)


class SendButton(QPushButton):
    """ct2 蓝色圆形发送按钮：acc 底 + 白色 ↗ 箭头（QPainter 绘制）"""

    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        acc = QColor(toks.get("acc", "#3880F0"))
        acc_hi = QColor(toks.get("acc_hi", "#2B6FE4"))
        acc_soft = QColor(toks.get("acc_soft", "#EAF1FD"))
        ink = QColor(toks.get("acc_ink", "#FFFFFF"))
        dim = QColor(toks.get("dim", "#98A2B0"))
        hover = self.underMouse()
        enabled = self.isEnabled()
        bg = acc_hi if hover else acc
        if not enabled:
            bg = acc_soft
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        p.drawEllipse(r)
        c = self.width() / 2.0
        pen = QPen(ink if enabled else dim, 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        # ↗ 发送箭头
        p.drawLine(QPointF(c - 3.5, c + 4.5), QPointF(c + 4.5, c - 4.5))
        p.drawLine(QPointF(c - 2.0, c - 4.5), QPointF(c + 4.5, c - 4.5))
        p.drawLine(QPointF(c + 4.5, c - 4.5), QPointF(c + 4.5, c + 3.0))


class DeviceCard(QFrame):
    """主页车型卡：QPainter 图标 + 名称 + 副标题，单选高亮，点击发信号。"""

    clicked = Signal(str)

    def __init__(self, key: str, label: str, sub: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._label = label
        self.setObjectName("DevCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(170, 152)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 16, 12, 14)
        v.setSpacing(6)
        gly = VehicleGlyph(key, size=46)
        v.addWidget(gly, 0, Qt.AlignCenter)
        name = QLabel(label)
        name.setObjectName("DevCardName")
        name.setAlignment(Qt.AlignCenter)
        v.addWidget(name)
        sub_lbl = QLabel(sub)
        sub_lbl.setObjectName("DevCardSub")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setWordWrap(True)
        v.addWidget(sub_lbl)
        _prop(self, "sel", "off")

    @property
    def vehicle_key(self) -> str:
        return self._key

    @property
    def label(self) -> str:
        return self._label

    def set_selected(self, sel: bool):
        _prop(self, "sel", "on" if sel else "off")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


class HomePage(QWidget):
    """ct1 主页·设备选择：标题 + 四张车型卡（轿车/SUV/卡车/新能源）+ 底部免责声明。"""

    device_selected = Signal(str)   # 车型 key: car/suv/truck/ev

    VEHICLES = [
        ("car", "轿车", "家用代步 · 商务通勤"),
        ("suv", "SUV", "越野 · 户外出行"),
        ("truck", "卡车", "货运 · 工程作业"),
        ("ev", "新能源", "纯电 · 混动"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._selected = None
        self._cards = []
        self._build_ui()
        self._select("car")   # 默认选中「轿车」（不触发导航）

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 48, 24, 24)
        root.setSpacing(8)
        root.addStretch(2)

        title = QLabel("选择您使用的设备")
        title.setObjectName("HomeTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        sub = QLabel("点击车型卡片，进入自动化采集与 AI 诊断")
        sub.setObjectName("HomeSub")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(30)

        row = QHBoxLayout()
        row.setSpacing(18)
        row.addStretch(1)
        for key, label, sub_txt in self.VEHICLES:
            card = DeviceCard(key, label, sub_txt)
            card.clicked.connect(self._on_card)
            self._cards.append(card)
            row.addWidget(card)
        row.addStretch(1)
        root.addLayout(row)

        root.addStretch(3)
        foot = QLabel("AutoDiag AI 提供的建议仅供参考，重大故障请前往专业维修店检修")
        foot.setObjectName("HomeSub")
        foot.setAlignment(Qt.AlignCenter)
        root.addWidget(foot)

    def _select(self, key: str):
        """仅更新卡片选中态，不触发导航"""
        for c in self._cards:
            c.set_selected(c.vehicle_key == key)
        self._selected = key

    def _on_card(self, key: str):
        self._select(key)
        label = dict((k, l) for k, l, _ in self.VEHICLES).get(key, "")
        self.device_selected.emit(label)   # 发中文车型名（面包屑/摘要/AI 上下文共用）

    def selected_vehicle(self) -> str:
        """返回已选车型中文名；未选返回空串"""
        for key, label, _ in self.VEHICLES:
            if key == self._selected:
                return label
        return ""


# ═══════════════════════════════════════════════════════════
#  RunPage  ①运行
# ═══════════════════════════════════════════════════════════

class RunPage(QWidget):
    cancel_requested = Signal()

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
        icon = QLabel("DTS")
        icon.setObjectName("DevIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(42, 42)
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
        self._status_lbl = QLabel("填写故障现象后点击发送，将自动执行采集 + AI 分析")
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
            self._status_lbl.setText("流程结束 — 可查看数据 / 诊断分析")

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
#  AiPage  ③诊断分析：三段式诊断（采集计划 → 路试判断 → 维修报告）
# ═══════════════════════════════════════════════════════════

_STAGES = {
    1: ("确认采集列表", "选择数据流与采集工况"),
    2: ("是否需要路试", "判断原地数据能否定位"),
    3: ("输出维修报告", "生成排查方案"),
}


def _rich(text) -> str:
    """转义模型文本，仅放行 <b>/<strong>/<br> 标签（QLabel 富文本可渲染）"""
    esc = _html.escape(str(text))
    for tag in ("br", "br/", "br /"):
        esc = esc.replace(f"&lt;{tag}&gt;", "<br>")
    esc = esc.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    esc = esc.replace("&lt;strong&gt;", "<b>").replace("&lt;/strong&gt;", "</b>")
    esc = esc.replace("\r\n", "\n").replace("\n", "<br>")
    return esc


class AiPage(QWidget):
    """③诊断分析：问题输入条 → 三段式诊断链路 → 维修报告（结果 widget 渲染）"""

    start_requested = Signal()    # 用户点发送 → wizard 起完整流程（采集 + AI）
    restart_requested = Signal()  # 用户点「重新诊断」→ 清空结果回到输入
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

        # ── 头部（ct2）：AI 诊断结果 + 数据计数 + 状态徽标 ──
        self._stack_layout.insertLayout(0, self._header_row())
        self._stack_layout.insertWidget(1, self._summary_bar())   # 车型：轿车 | 问题：…
        self._stack_layout.insertWidget(2, self._input_card())    # FAQ + ✦输入条 + 圆形发送
        self._stack_layout.insertLayout(3, _section_header("诊断链路"))
        self._stack_layout.insertWidget(4, self._stage_timeline())
        self._stack_layout.insertWidget(5, self._plan_card())
        self._stack_layout.insertWidget(6, self._loc_card())
        self._stack_layout.insertWidget(7, self._report_card())
        self._stack_layout.insertWidget(8, self._action_card())   # 重新诊断 + 导出诊断报告

        # ── 页脚说明 ──
        self._stack_layout.insertLayout(9, self._footer_row())

    def _header_row(self) -> QHBoxLayout:
        head = QHBoxLayout()
        title = QLabel("AI 诊断结果")
        title.setObjectName("SecTitle")
        title.setStyleSheet("font-size: 15px;")
        head.addWidget(title)
        head.addStretch(1)
        self._sum_lbl = QLabel("等待运行数据")
        self._sum_lbl.setObjectName("SecCount")
        head.addWidget(self._sum_lbl)
        self._ai_badge = QLabel("")
        self._ai_badge.setObjectName("AiBadge")
        self._ai_badge.setVisible(False)
        head.addWidget(self._ai_badge)
        return head

    def _summary_bar(self) -> QFrame:
        """ct2 摘要条：车型：轿车 | 问题：…"""
        bar = QFrame()
        bar.setObjectName("SummaryBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(8)
        self._summary_lbl = QLabel("")
        self._summary_lbl.setObjectName("SummaryText")
        h.addWidget(self._summary_lbl)
        h.addStretch(1)
        bar.setVisible(False)
        return bar

    def set_summary(self, vehicle: str, symptom: str):
        """设置摘要条；vehicle / symptom 为空时对应段省略"""
        self._vehicle_label = vehicle
        parts = [p for p in (f"车型：{vehicle}" if vehicle else "",
                             f"问题：{symptom}" if symptom else "") if p]
        self._summary_lbl.setText("　｜　".join(parts) or "车型：—")
        self._summary_bar_ref().setVisible(bool(parts))

    def _input_card(self) -> QFrame:
        """ct2 输入条：FAQ 快捷描述（2×3）+ ✦ 单行输入 + 回形针 + 蓝色圆形发送"""
        card = QFrame()
        card.setObjectName("AiCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        # FAQ 快捷描述（2×3，点击自动填入输入框）
        faq = QGridLayout()
        faq.setSpacing(8)
        for i, q in enumerate(("发动机抖动", "动力不足", "故障灯亮",
                               "启动困难", "油耗偏高", "行驶异响")):
            chip = QPushButton(q)
            chip.setObjectName("FaqChip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _=False, text=q: self._apply_faq(text))
            faq.addWidget(chip, i // 3, i % 3)
        v.addLayout(faq)

        # 输入条：✦ + 单行输入 + 回形针 + 圆形发送
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(SparkIcon())
        self._symptom_input = QLineEdit()
        self._symptom_input.setObjectName("InputBar")
        self._symptom_input.setPlaceholderText("描述您遇到的故障现象…")
        self._symptom_input.returnPressed.connect(self.start_requested)
        bar.addWidget(self._symptom_input, 1)
        bar.addWidget(ClipIcon())
        self._run_btn = SendButton()
        self._run_btn.setObjectName("SendBtn")
        self._run_btn.setEnabled(True)
        self._run_btn.clicked.connect(self.start_requested)
        bar.addWidget(self._run_btn)
        v.addLayout(bar)

        # 补充说明（可选）
        lbl2 = QLabel("补充说明（可选）")
        lbl2.setObjectName("AiHeader")
        v.addWidget(lbl2)
        self._notes_input = QLineEdit()
        self._notes_input.setObjectName("InputBar")
        self._notes_input.setPlaceholderText(
            "例：已做过的维修、车辆配置、未安装的部件、特殊工况等。")
        v.addWidget(self._notes_input)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._status_lbl = QLabel("填写故障现象后点击发送，将自动执行采集 + AI 分析")
        self._status_lbl.setObjectName("DtcDesc")
        row.addWidget(self._status_lbl)
        row.addStretch(1)
        v.addLayout(row)
        return card

    def _apply_faq(self, text: str):
        self._symptom_input.setText(text)
        self._status_lbl.setText(f"已填入：{text}")

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
        # 结果区用 widget 布局逐项渲染（真实 diagnosisList），随内容自适应高度
        body = QWidget()
        self._report_body = QVBoxLayout(body)
        self._report_body.setContentsMargins(0, 0, 0, 0)
        self._report_body.setSpacing(10)
        v.addWidget(body)
        card.setVisible(False)
        return card

    def _action_card(self) -> QFrame:
        """ct2 底部操作：重新诊断（灰描边）+ 导出诊断报告（蓝色主按钮）"""
        card = QFrame()
        card.setObjectName("ActionBar")
        h = QHBoxLayout(card)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        self._restart_btn = QPushButton("重新诊断")
        self._restart_btn.setObjectName("Ghost")
        self._restart_btn.setCursor(Qt.PointingHandCursor)
        self._restart_btn.clicked.connect(self.restart_requested)
        h.addWidget(self._restart_btn)
        self._export_btn = QPushButton("导出诊断报告")
        self._export_btn.setObjectName("Primary")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.clicked.connect(self._on_export)
        h.addWidget(self._export_btn)
        h.addStretch(1)
        card.setVisible(False)
        return card

    def _on_export(self):
        """把真实维修报告导出为 Markdown 文件（面向用户的交付物）"""
        data = getattr(self, "_report_data", None)
        if not data:
            self._status_lbl.setText("暂无诊断结果可导出")
            return
        default = f"AutoDrive_诊断报告_{datetime.now():%Y%m%d_%H%M%S}.md"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出诊断报告", str(Path.home() / default),
            "Markdown (*.md);;文本文件 (*.txt)")
        if not path:
            return
        lines = ["# AutoDrive 诊断报告", ""]
        if self._vehicle_label:
            lines.append(f"- 车型：{self._vehicle_label}")
        sym = self._symptom_input.text().strip()
        if sym:
            lines.append(f"- 故障现象：{sym}")
        lines.append("")
        concl = (data.get("overallConclusion") or "").strip()
        if concl:
            lines.append("## 综合结论")
            lines.append(concl)
            lines.append("")
        diags = data.get("diagnosisList") or []
        if diags:
            lines.append("## 可能原因与排查建议")
            for i, d in enumerate(diags, 1):
                lines.append(f"{i}. **{d.get('faultPoint') or '—'}**"
                             f"（{d.get('probability') or '—'}）")
                expl = (d.get("simpleExplanation") or "").strip()
                if expl:
                    lines.append(f"   诊断逻辑：{expl}")
                for s in (d.get("guideSteps") or []):
                    if s:
                        lines.append(f"   - {s}")
                lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self._status_lbl.setText(f"报告已导出：{Path(path).name}")

    def _footer_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        note = QLabel("分析基于本次采集的故障码与数据流 · 结果仅供辅助判断，不构成维修结论")
        note.setObjectName("DtcDesc")
        row.addWidget(note)
        return row

    # ── 对外接口 ──────────────────────────────────────

    def get_input(self):
        """返回 (故障现象, 补充说明)"""
        return (self._symptom_input.text().strip(),
                self._notes_input.text().strip())

    def focus_input(self):
        self._symptom_input.setFocus()

    def set_report(self, report: Report | None):
        self._report = report
        has = report is not None and report.has_data
        self._run_btn.setEnabled(not self._running)
        if has:
            self._sum_lbl.setText(
                f"基于 {len(report.faults)} 条故障码 + {len(report.flows)} 项数据流")
            self._status_lbl.setText("采集完成后将自动开始分析，也可手动填写现象后开始")
            out_dir = getattr(report, "out_dir", None)
            if out_dir and not self._running:
                self.load_from(out_dir)
        else:
            self._sum_lbl.setText("等待运行数据")
            self._status_lbl.setText("填写故障现象后点击发送，将自动执行采集 + AI 分析")

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
        """开始新一轮诊断：清空结果、状态归位（发送按钮始终可用，发送即采集+AI）"""
        self._running = False
        self._run_btn.setEnabled(True)
        self._status_lbl.setText("填写故障现象后点击发送，将自动执行采集 + AI 分析")
        self._plan_card_ref().setVisible(False)
        self._loc_card_ref().setVisible(False)
        self._report_card_ref().setVisible(False)
        self._action_card_ref().setVisible(False)
        self.set_badge("")
        self._clear_report_body()
        for no in _STAGES:
            self._set_stage(no, "pending", "")

    def set_running(self, running: bool):
        self._running = running
        self._run_btn.setEnabled(not running)
        self.set_badge("running" if running else "")
        if running:
            self._status_lbl.setText("诊断中…")

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
            note = QLabel("未返回推荐数据流")
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
        """渲染维修报告：结论 Hero + 逐条原因卡（真实 diagnosisList 文本，不伪造百分比）"""
        card = self._report_card_ref()
        card.setVisible(True)
        self._report_data = data
        self.set_badge("done")
        self._action_card_ref().setVisible(True)
        self._render_report(data)

    def set_badge(self, state: str):
        """分析状态徽标：running=分析中…(灰) / done=分析完成(绿) / 空=隐藏"""
        if state == "running":
            self._ai_badge.setText("分析中…")
            _prop(self._ai_badge, "state", "running")
            self._ai_badge.setVisible(True)
        elif state == "done":
            self._ai_badge.setText("分析完成")
            _prop(self._ai_badge, "state", "done")
            self._ai_badge.setVisible(True)
        else:
            self._ai_badge.setVisible(False)

    def show_error(self, msg: str):
        self._status_lbl.setText(f"诊断失败：{msg}")
        self.set_badge("")
        # 正在运行的阶段标红
        for no in _STAGES:
            row, icon, name_lbl, note_lbl = self._stage_rows[no]
            if icon.text() == ICONS.get("running"):
                self._set_stage(no, "error", "失败")
        self._run_btn.setEnabled(True)   # 允许重试

    # ── 私有：卡片引用 + 报告 widget 渲染 ───────────────

    def _summary_bar_ref(self):
        return self._stack_layout.itemAt(1).widget()

    def _input_card_ref(self):
        return self._stack_layout.itemAt(2).widget()

    def _plan_card_ref(self):
        return self._stack_layout.itemAt(5).widget()

    def _loc_card_ref(self):
        return self._stack_layout.itemAt(6).widget()

    def _report_card_ref(self):
        return self._stack_layout.itemAt(7).widget()

    def _action_card_ref(self):
        return self._stack_layout.itemAt(8).widget()

    def _clear_report_body(self):
        while self._report_body.count():
            item = self._report_body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_report(self, data: dict):
        """把真实 stage3 输出渲染进报告卡：结论 Hero → 逐条原因卡 → 底部弹性留白"""
        self._clear_report_body()
        tm = ThemeManager.instance()
        toks = tm.tokens if tm is not None else {}
        mut = toks.get("mut", "#5B6573")

        concl = (data.get("overallConclusion") or "").strip()
        if concl:
            hero = QFrame()
            hero.setObjectName("ConclHero")
            hv = QVBoxLayout(hero)
            hv.setContentsMargins(16, 14, 16, 14)
            lbl = QLabel()
            lbl.setObjectName("ConclTitle")
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            lbl.setText(f"<span style='line-height:1.8;'>{_rich(concl)}</span>")
            hv.addWidget(lbl)
            self._report_body.addWidget(hero)

        diags = data.get("diagnosisList") or []
        if not diags:
            note = QLabel("（未返回具体排查条目）")
            note.setObjectName("DtcDesc")
            self._report_body.addWidget(note)
        for i, d in enumerate(diags, 1):
            self._report_body.addWidget(self._make_cause_card(i, d, toks))
        self._report_body.addStretch(1)

    def _make_cause_card(self, i: int, d: dict, toks: dict) -> QFrame:
        """单条可能原因卡：排名圆标 + 病灶名 + 可能性标签 + 诊断逻辑 + 排查处方"""
        card = QFrame()
        card.setObjectName("CauseCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        rank = QLabel(str(i))
        rank.setObjectName("CauseRank")
        rank.setFixedSize(26, 26)
        rank.setAlignment(Qt.AlignCenter)
        head.addWidget(rank)
        name = QLabel(str(d.get("faultPoint") or "—"))
        name.setObjectName("CauseName")
        name.setWordWrap(True)
        head.addWidget(name, 1)
        prob_text = (d.get("probability") or "").strip()
        if prob_text:
            prob = QLabel(prob_text)
            prob.setObjectName("CauseProb")
            _prop(prob, "pl", self._prob_level(prob_text))
            head.addWidget(prob)
        v.addLayout(head)

        mut = toks.get("mut", "#5B6573")
        expl = (d.get("simpleExplanation") or "").strip()
        if expl:
            lbl = QLabel()
            lbl.setObjectName("GuideText")
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            lbl.setText(f"<span style='color:{mut};'>诊断逻辑：{_rich(expl)}</span>")
            v.addWidget(lbl)

        steps = d.get("guideSteps") or []
        if steps:
            head_lbl = QLabel("排查处方")
            head_lbl.setObjectName("CauseStepsHead")
            v.addWidget(head_lbl)
            for s in steps:
                s = (s or "").strip()
                if not s:
                    continue
                row = QFrame()
                row.setObjectName("GuideRow")
                rh = QHBoxLayout(row)
                rh.setContentsMargins(0, 0, 0, 0)
                rh.setSpacing(8)
                ck = QLabel("✓")
                ck.setObjectName("GuideCheck")
                ck.setFixedSize(18, 18)
                ck.setAlignment(Qt.AlignCenter)
                rh.addWidget(ck)
                tl = QLabel()
                tl.setObjectName("GuideText")
                tl.setTextFormat(Qt.RichText)
                tl.setWordWrap(True)
                tl.setText(_rich(s))
                rh.addWidget(tl, 1)
                v.addWidget(row)
        return card

    @staticmethod
    def _prob_level(text: str) -> str:
        """把模型返回的可能性文字映射到标签层级：high / mid / low

        覆盖 stage3 模板里的真实词汇：可能性最大 → 红、次高/值得怀疑/可能性较大 → 橙、
        较少/较低/可能性较小 → 蓝。
        """
        t = (text or "").strip()
        if any(k in t for k in ("可能性最大", "概率最大", "可能性大", "极大",
                                "非常高", "优先", "首推", "首要")):
            return "high"
        if any(k in t for k in ("可能性较大", "概率较大", "较可", "较有",
                                "次高", "值得", "怀疑", "不排", "其次", "中等")):
            return "mid"
        return "low"

    def _report_texts(self) -> str:
        """报告区全部 QLabel 文本拼接，供测试断言真实渲染内容"""
        card = self._report_card_ref()
        return " ".join(w.text() for w in card.findChildren(QLabel) if w.text())


# ═══════════════════════════════════════════════════════════
#  DiagnosticPage  单页连续诊断流（去掉分页切换）
#  ①采集运行 → ②采集结果(紧凑摘要+可展开) → ③诊断分析，随流程推进自动展开。
# ═══════════════════════════════════════════════════════════

class DiagnosticPage(QWidget):
    """ct2 分析页：面包屑 + 四节点步进器 + 单页连续诊断流（①采集运行→②采集结果→③诊断分析）。"""

    start_requested = Signal()    # 内嵌 AiPage 转发（发送 → 采集 + AI）
    cancel_requested = Signal()   # 内嵌 RunPage 转发（取消 DTS）
    back_requested = Signal()     # 面包屑「‹ 返回」→ 主页

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

        # ── 面包屑（ct2）：‹ 返回 / 车型 诊断 ──
        crumb = QHBoxLayout()
        crumb.setContentsMargins(24, 10, 24, 0)
        crumb.setSpacing(8)
        self._back_btn = QPushButton("‹  返回")
        self._back_btn.setObjectName("CrumbBack")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_requested)
        crumb.addWidget(self._back_btn)
        self._crumb_lbl = QLabel("车辆 诊断")
        self._crumb_lbl.setObjectName("CrumbText")
        crumb.addWidget(self._crumb_lbl)
        crumb.addStretch(1)
        root.addLayout(crumb)

        # ── ct2 四节点步进器（纯展示） ──
        self._phase_bar = PhaseBar()
        root.addWidget(self._phase_bar)

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

        # ── ③ 诊断分析（有数据后启用） ──
        self.ai = AiPage(embed=True)
        self.ai.start_requested.connect(self.start_requested)
        self.ai.setVisible(False)
        self._content.addWidget(self.ai)

        self._scroll.setWidget(content)
        root.addWidget(self._scroll)

    # ── 对外接口 ──────────────────────────────────────

    def set_vehicle(self, vehicle: str):
        """面包屑显示「{车型} 诊断」"""
        self._crumb_lbl.setText(f"{vehicle} 诊断")

    def set_phase(self, phase: str):
        self._phase_bar.set_phase(phase)

    def set_back_enabled(self, enabled: bool):
        self._back_btn.setEnabled(enabled)

    def set_report(self, report: Report | None):
        """报告就绪：渲染数据明细 + 诊断结果恢复，按 has_data 显示②③节"""
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
        """新一次 DTS 前调用：收起②③节、清空诊断结果"""
        self._data_section.setVisible(False)
        self.ai.setVisible(False)
        self.data.setVisible(False)
        self._toggle_btn.setText("▸ 展开明细")
        self.ai.reset()

    def scroll_to(self, widget):
        """延迟到布局稳定后把 widget 滚入可视区（自动跟随当前阶段）"""
        QTimer.singleShot(0, lambda: self._scroll.ensureWidgetVisible(widget, 60, 60))
