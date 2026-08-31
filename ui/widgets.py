"""
LCS700 基础控件（QPainter 绘制，无图片资源）。
"""

import math
import re
from functools import lru_cache

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ui.theme import ThemeManager

__all__ = [
    "_prop", "_set_prop_tree", "section_header", "_fade_in", "_slide_up",
    "ClickFrame", "SvgGlyph", "RunchLogo", "SparkIcon", "ClipIcon", "SendButton", "DeviceGlyph",
    "IconBox",
    "PhaseBar", "GlassCard", "SectionTitle", "StatusTag", "GradBar", "DevCard", "Toast",
]


def _prop(widget, name, value):
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    return widget


def _set_prop_tree(widget, name, value):
    """设置属性并连同子控件一起重新 polish。

    后代选择器（如 QFrame[sel="on"] QLabel#xx）只在子控件自身 polish 时重算样式，
    仅 repolish 父控件不会让子 QLabel 的选中态生效。"""
    _prop(widget, name, value)
    style = widget.style()
    for child in widget.findChildren(QWidget):
        style.unpolish(child)
        style.polish(child)
        child.update()
    return widget


class ClickFrame(QFrame):
    """可点击容器：QPushButton 的 sizeHint 由 QStyleOptionButton（空文本）决定，
    会忽略内部 layout，导致 logo/头像等子控件溢出重叠；QFrame 的 sizeHint 来自
    layout，配合点击信号即可当作"带子布局的可点按钮"使用。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _tokens() -> dict:
    tm = ThemeManager.instance()
    return tm.tokens if tm is not None else {}


# ═══════════════════════════════════════════════════════════
#  入场动效：淡入 / 上滑（Toast / ModalScrim 用）
# ═══════════════════════════════════════════════════════════

def _fade_in(widget, duration: int = 180):
    _animate_show(widget, duration, dy=0)


def _slide_up(widget, duration: int = 200, dy: int = 14):
    """上滑入场：从当前位下方 dy 像素淡入到位。调用前须先把 widget 定好位。"""
    _animate_show(widget, duration, dy=dy)


def _animate_show(widget, duration: int, dy: int):
    # Qt 语义：setGraphicsEffect(new/None) 会自动删除旧的 effect（已实测验证），
    # 因此绝不再 deleteLater 旧 effect，防止双删崩溃。
    eff = QGraphicsOpacityEffect(widget)
    eff.setOpacity(0.0)
    widget.setGraphicsEffect(eff)
    if dy:
        widget.move(widget.x(), widget.y() + dy)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    def _done():
        widget.setGraphicsEffect(None)   # 自动删除 eff
        anim.deleteLater()
        widget._fade_anim = None

    anim.finished.connect(_done)
    widget._fade_anim = anim
    anim.start()


def section_header(text, count="") -> QHBoxLayout:
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


# ═══════════════════════════════════════════════════════════
#  SvgGlyph  SVG 路径迷你解析器
# ═══════════════════════════════════════════════════════════

_PATH_TOKEN = re.compile(r"([MLHVZCQSTAmlhvzcqsta]|-?\d*\.?\d+(?:e[-+]?\d+)?)")
_CMDS = set("MLHVZCQSTAmlhvzcqsta")
_ISNUM = re.compile(r"^-?\d")
_ELEM_RE = re.compile(r"<(\w+)([^>]*)>")


def _arc_to(path: "QPainterPath", x, y, rx, ry, rot, large, sweep, ex, ey):
    """SVG 椭圆弧 → 中心参数化 → 折线近似（小图标足够）。"""
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or (x == ex and y == ey):
        path.lineTo(ex, ey)
        return
    phi = math.radians(rot)
    dx2, dy2 = (x - ex) / 2, (y - ey) / 2
    cp, sp = math.cos(phi), math.sin(phi)
    x1p, y1p = cp * dx2 + sp * dy2, -sp * dx2 + cp * dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = max(0.0, rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(num / den) if den else 0.0
    if large == sweep:
        coef = -coef
    cxp, cyp = coef * (rx * y1p / ry), coef * (-ry * x1p / rx)
    cx, cy = cp * cxp - sp * cyp + (x + ex) / 2, sp * cxp + cp * cyp + (y + ey) / 2

    def _ang(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    th1 = _ang(1, 0, ux, uy)
    dth = _ang(ux, uy, vx, vy)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    steps = 16
    for k in range(1, steps + 1):
        t = th1 + dth * k / steps
        px = cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp
        py = cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp
        path.lineTo(px, py)
    path.lineTo(ex, ey)


@lru_cache(maxsize=256)
def _svg_path(d: str) -> QPainterPath:
    """解析 SVG path data 为 QPainterPath（M/L/H/V/C/Q/Z + S/T/A + 相对小写）。

    覆盖实际图标集全部命令；未知命令直接跳过（安全回落）。
    lru_cache：同一图标 markup 被多实例复用，只解析一次（QPainterPath 只读绘制，缓存安全）。
    """
    path = QPainterPath()
    toks = _PATH_TOKEN.findall(d or "")
    i, n = 0, len(toks)
    x = y = sx = sy = 0.0
    px2 = py2 = 0.0        # 上一次 cubic 的第二个控制点（S/T 反射用）
    pending = None

    def num():
        nonlocal i
        while i < n and not _ISNUM.match(toks[i]):
            i += 1
        if i >= n:
            raise ValueError("svg path: missing number")
        v = float(toks[i])
        i += 1
        return v

    def nums(k):
        return [num() for _ in range(k)]

    def r(a, b):
        """绝对坐标（相对命令加当前点）。"""
        return a if cmd.isupper() else a + x, b if cmd.isupper() else b + y

    while i < n:
        t = toks[i]
        if t in _CMDS:
            cmd = t
            i += 1
        else:
            cmd = pending
            if cmd is None:
                break
        pending = cmd
        u = cmd.lower()
        if u == "z":
            path.closeSubpath()
            x, y = sx, sy
            pending = None
            continue
        if u == "m":
            dx, dy = nums(2)
            nx, ny = r(dx, dy)
            path.moveTo(nx, ny)
            sx, sy = nx, ny
            x, y = nx, ny
            pending = "L" if cmd.isupper() else "l"
        elif u == "l":
            dx, dy = nums(2)
            nx, ny = r(dx, dy)
            path.lineTo(nx, ny)
            x, y = nx, ny
            px2 = py2 = 0.0
        elif u == "h":
            dx = nums(1)[0]
            nx = dx if cmd.isupper() else x + dx
            path.lineTo(nx, y)
            x = nx
        elif u == "v":
            dy = nums(1)[0]
            ny = dy if cmd.isupper() else y + dy
            path.lineTo(x, ny)
            y = ny
        elif u == "c":
            x1, y1, x2, y2, ex, ey = nums(6)
            x1, y1 = r(x1, y1)
            x2, y2 = r(x2, y2)
            ex, ey = r(ex, ey)
            path.cubicTo(x1, y1, x2, y2, ex, ey)
            px2, py2 = x2, y2
            x, y = ex, ey
        elif u == "s":    # 平滑三次曲线：控制点1 = 上次控制点2 关于当前点反射
            x2, y2, ex, ey = nums(4)
            x2, y2 = r(x2, y2)
            ex, ey = r(ex, ey)
            x1 = 2 * x - px2
            y1 = 2 * y - py2
            path.cubicTo(x1, y1, x2, y2, ex, ey)
            px2, py2 = x2, y2
            x, y = ex, ey
        elif u == "q":
            cx, cy, ex, ey = nums(4)
            cx, cy = r(cx, cy)
            ex, ey = r(ex, ey)
            path.quadTo(cx, cy, ex, ey)
            x, y = ex, ey
        elif u == "t":    # 平滑二次曲线：控制点 = 上次二次控制点关于当前点反射
            ex, ey = nums(2)
            ex, ey = r(ex, ey)
            cx = 2 * x - px2
            cy = 2 * y - py2
            path.quadTo(cx, cy, ex, ey)
            x, y = ex, ey
        elif u == "a":
            rx, ry, rot, large, sweep, ex, ey = nums(7)
            ex, ey = r(ex, ey)
            _arc_to(path, x, y, rx, ry, rot, int(large), int(sweep), ex, ey)
            x, y = ex, ey
        else:
            break
    return path


@lru_cache(maxsize=256)
def _parse_markup(markup: str) -> list:
    """解析 <path>/<circle>/<rect>/<polyline> → [(kind, data)]"""
    items = []
    for tag, attrs in _ELEM_RE.findall(markup or ""):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
        if tag == "path":
            items.append(("path", _svg_path(a.get("d", ""))))
        elif tag == "circle":
            items.append(("circle", (
                float(a.get("cx", 0)), float(a.get("cy", 0)), float(a.get("r", 0)))))
        elif tag == "rect":
            items.append(("rect", (
                float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("width", 0)),
                float(a.get("height", 0)), float(a.get("rx", 0)))))
        elif tag == "polyline":
            pts = [float(v) for v in (a.get("points", "") or "").replace(",", " ").split()]
            p = QPainterPath()
            if len(pts) >= 2:
                p.moveTo(pts[0], pts[1])
                for k in range(2, len(pts) - 1, 2):
                    p.lineTo(pts[k], pts[k + 1])
            items.append(("path", p))
    return items


class SvgGlyph(QWidget):
    """把 SVG inner-markup 绘成描边线稿。stroke 为令牌名（如 "acc"/"mut"），主题切换自动重绘。"""

    def __init__(self, markup: str, size: int = 24, stroke: str = "mut",
                 stroke_w: float = 1.7, viewbox: int = 24, parent=None):
        super().__init__(parent)
        self._markup = markup
        self._stroke = stroke
        self._stroke_w = stroke_w
        self._viewbox = viewbox
        self._items = _parse_markup(markup)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        toks = _tokens()
        color = QColor(toks.get(self._stroke, "#9ca3af"))
        vb = self._viewbox or 1
        p.scale(self.width() / float(vb), self.height() / float(vb))
        pen = QPen(color, self._stroke_w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for kind, data in self._items:
            if kind == "path":
                p.drawPath(data)
            elif kind == "circle":
                cx, cy, r = data
                p.drawEllipse(QPointF(cx, cy), r, r)
            elif kind == "rect":
                x, y, w, h, rx = data
                p.drawRoundedRect(QRectF(x, y, w, h), rx, rx)


# ═══════════════════════════════════════════════════════════
#  RunchLogo  远驰渐变圆角块 + 白色闪电
# ═══════════════════════════════════════════════════════════

class RunchLogo(QWidget):
    def __init__(self, size: int = 34, parent=None):
        super().__init__(parent)
        self.setObjectName("RunchLogo")
        self.setFixedSize(size, size)
        # 几何与闪电 path 与尺寸绑定，构造期缓存一次（paint 只差令牌颜色）
        s = float(size)
        m = max(1.0, s * 0.04)
        self._rect = QRectF(m, m, s - 2 * m, s - 2 * m)
        self._radius = s * 0.24
        c = s / 2.0
        bolt = QPainterPath()
        bolt.moveTo(c + s * 0.04, self._rect.top() + s * 0.06)
        bolt.lineTo(c - s * 0.10, c + s * 0.02)
        bolt.lineTo(c + s * 0.00, c + s * 0.02)
        bolt.lineTo(c - s * 0.04, self._rect.bottom() - s * 0.06)
        bolt.lineTo(c + s * 0.12, c - s * 0.04)
        bolt.lineTo(c + s * 0.02, c - s * 0.04)
        bolt.closeSubpath()
        self._bolt = bolt

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        toks = _tokens()
        g0 = QColor(toks.get("acc_grad0", "#38bdf8"))
        g1 = QColor(toks.get("acc_grad1", "#2563eb"))
        p.setPen(Qt.NoPen)
        lg = QLinearGradient(self._rect.topLeft(), self._rect.bottomRight())
        lg.setColorAt(0.0, g0)
        lg.setColorAt(1.0, g1)
        p.setBrush(lg)
        p.drawRoundedRect(self._rect, self._radius, self._radius)
        p.setBrush(QColor("#FFFFFF"))
        p.drawPath(self._bolt)


# ═══════════════════════════════════════════════════════════
#  SparkIcon / ClipIcon / SendButton（AI 输入条）
# ═══════════════════════════════════════════════════════════

class SparkIcon(QWidget):
    """四角星 ✦：输入条前缀图标"""

    def __init__(self, size: int = 18, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        c = size / 2.0
        s = size / 2.0 - 2
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
        self._path = path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        toks = _tokens()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(toks.get("mut", "#9ca3af")))
        p.drawPath(self._path)


class ClipIcon(QWidget):
    """回形针：输入条装饰图标"""

    def __init__(self, size: int = 18, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        c = size / 2.0
        s = size / 2.0 - 2
        path = QPainterPath()
        path.moveTo(c - s * 0.45, c + s * 0.30)
        path.lineTo(c - s * 0.45, c - s * 0.25)
        path.arcTo(QRectF(c - s * 0.45, c - s * 0.35, s * 0.60, s * 0.60), 180, -180)
        path.lineTo(c + s * 0.30, c + s * 0.05)
        self._path = path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        toks = _tokens()
        pen = QPen(QColor(toks.get("dim", "#6b7280")), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(self._path)


class SendButton(QPushButton):
    """渐变圆形发送按钮：acc 渐变底 + 白色 ↗ 箭头"""

    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        # 箭头端点与尺寸绑定，构造期缓存一次
        c = size / 2.0
        self._arrow = [
            (QPointF(c - 3.5, c + 4.5), QPointF(c + 4.5, c - 4.5)),
            (QPointF(c - 2.0, c - 4.5), QPointF(c + 4.5, c - 4.5)),
            (QPointF(c + 4.5, c - 4.5), QPointF(c + 4.5, c + 3.0)),
        ]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        toks = _tokens()
        g0 = QColor(toks.get("acc_grad0", "#38bdf8"))
        g1 = QColor(toks.get("acc_grad1", "#2563eb"))
        ink = QColor(toks.get("acc_ink", "#FFFFFF"))
        dim = QColor(toks.get("dim", "#6b7280"))
        enabled = self.isEnabled()
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        p.setPen(Qt.NoPen)
        if not enabled:
            p.setBrush(QColor(toks.get("line", "#232a34")))
        else:
            lg = QLinearGradient(r.topLeft(), r.bottomRight())
            lg.setColorAt(0.0, g0)
            lg.setColorAt(1.0, g1)
            p.setBrush(lg)
        p.drawEllipse(r)
        pen = QPen(ink if enabled else dim, 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for p1, p2 in self._arrow:
            p.drawLine(p1, p2)
        # hover / 按下光环（自绘控件无 QSS hover，读 Qt 状态）
        if enabled and (self.underMouse() or self.isDown()):
            ring = QColor(toks.get("acc", "#38bdf8"))
            ring.setAlpha(70 if not self.isDown() else 120)
            p.setPen(QPen(ring, 2.0))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))


class DeviceGlyph(SvgGlyph):
    """设备 SVG 图标便捷封装：默认强调色描边。"""

    def __init__(self, icon: str, size: int = 44, stroke: str = "acc",
                 icon_map: dict | None = None, parent=None):
        from ui.lcsdata import DEV_ICONS
        markup = (icon_map or DEV_ICONS).get(icon, "")
        super().__init__(markup, size=size, stroke=stroke, viewbox=24, parent=parent)


class IconBox(QFrame):
    """彩色圆角小方块（对齐设计稿 .dev-card .pic / .quick-tile .ic）：
    语义色软底 + SVG 描边线稿，主题切换自动重绘。

    color ∈ acc/warn/ok/purple（对应 {color}_soft 底 + {color}_hi 描边）；
    size=36 设备卡、32 快捷宫格（theme.qss #IconBox[sz] 约束）。"""

    def __init__(self, markup: str = "", size: int = 36, color: str = "acc",
                 icon_size: int | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("IconBox")
        _prop(self, "ic", color)
        _prop(self, "sz", str(size))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        if markup:
            lay.addWidget(SvgGlyph(markup, size=icon_size or max(1, int(size * 0.56)),
                                   stroke=f"{color}_hi"))


# ═══════════════════════════════════════════════════════════
#  PhaseBar  数字 01-04 四节点步进器
# ═══════════════════════════════════════════════════════════

class PhaseBar(QFrame):
    """四节点步进器：done=绿 / current=渐变 / next=灰，只做状态提示。

    set_phase 映射（与旧 ct2 语义一致）：
      run     → ①✓ ②● ③ ④
      data/ai → ①✓ ②✓ ③● ④
      report  → ①✓ ②✓ ③✓ ④●
    """

    _PHASES = [
        ("01", "选择设备", "选择您使用的设备"),
        ("02", "描述问题", "自动识别或手动输入"),
        ("03", "AI 分析", "采集数据 + AI 分析"),
        ("04", "诊断报告", "生成排查建议"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stepsBar")
        self._dots = []
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 6, 16, 6)
        h.setSpacing(0)
        h.addStretch(1)
        for i, (num, label, sub) in enumerate(self._PHASES):
            if i:
                conn = QLabel("")
                conn.setObjectName("Conn")
                conn.setFixedSize(26, 2)
                h.addWidget(conn)
            dot = QLabel(num)
            dot.setObjectName("StepDot")
            dot.setFixedSize(26, 26)
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
        idx = {"run": 1, "data": 2, "ai": 2, "report": 3}.get(phase, 1)
        for i, (dot, lbl, sub) in enumerate(self._dots):
            state = "done" if i < idx else ("current" if i == idx else "next")
            for w in (dot, lbl, sub):
                _prop(w, "stepState", state)


# ═══════════════════════════════════════════════════════════
#  容器 / 标签 / 概率条 / 设备卡 / Toast
# ═══════════════════════════════════════════════════════════

class GlassCard(QFrame):
    """毛玻璃卡片容器（role="glass"）。"""

    def __init__(self, parent=None, padding: int = 16):
        super().__init__(parent)
        _prop(self, "role", "glass")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(padding, padding, padding, padding)
        self._lay.setSpacing(10)

    @property
    def layout(self):
        return self._lay


class SectionTitle(QLabel):
    """小节标题（可带右侧 count）。"""

    def __init__(self, text: str, count: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("SecTitle")
        if count:
            self.setText(f"{text}  ·  {count}")


class StatusTag(QLabel):
    """状态胶囊：kind ∈ ok / warn / crit / acc / muted。"""

    def __init__(self, text: str = "", kind: str = "muted", parent=None):
        super().__init__(text, parent)
        _prop(self, "role", "tag")
        self.set_kind(kind)

    def set_kind(self, kind: str):
        _prop(self, "kind", kind)


class GradBar(QWidget):
    """渐变概率条：value ∈ [0,1]，渐变填充。"""

    def __init__(self, parent=None, height: int = 6):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._value = 0.0
        self._color = None

    def set_value(self, value: float, color: str | None = None):
        self._value = max(0.0, min(1.0, float(value)))
        self._color = color
        self.update()

    def value(self) -> float:
        return self._value

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        toks = _tokens()
        bg = QColor(toks.get("line", "#232a34"))
        h = float(self.height())
        w = float(self.width())
        r = h / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)
        fw = w * self._value
        if fw > 0.5:
            g0 = QColor(toks.get("acc_grad0", "#38bdf8"))
            g1 = QColor(toks.get("acc_grad1", "#2563eb"))
            if self._color:
                g0 = g1 = QColor(self._color)
            from PySide6.QtGui import QLinearGradient
            lg = QLinearGradient(0, 0, fw, 0)
            lg.setColorAt(0.0, g0)
            lg.setColorAt(1.0, g1)
            p.setBrush(lg)
            p.drawRoundedRect(QRectF(0, 0, fw, h), r, r)


class DevCard(QFrame):
    """主页设备卡：居中彩色图标盒 + 名称 + 系统 + OBD，删除 × 绝对定位右上角。

    对齐设计稿 .dev-card：flex column + align-items:center（图标盒与三行文字水平居中），
    .del-btn position:absolute top:6 right:8（resizeEvent 定位，不参与布局流）。"""

    clicked = Signal(str)        # device id
    delete_requested = Signal(str)

    # 设备图标盒色（设计稿 .pic 变体）：cls="" → user 蓝
    _PIC_COLOR = {"orange": "warn", "green": "ok", "purple": "purple", "custom": "purple"}

    def __init__(self, dev: dict, parent=None):
        super().__init__(parent)
        from ui.lcsdata import DEV_ICONS
        self._dev = dev
        self.setCursor(Qt.PointingHandCursor)
        _prop(self, "card", "dev")
        _prop(self, "sel", "off")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)   # 内边距走 theme.qss [card="dev"] padding
        v.setSpacing(6)
        color = self._PIC_COLOR.get((dev.get("cls") or "").lower(), "acc")
        box = IconBox(DEV_ICONS.get(dev["icon"], ""), size=36, color=color)
        v.addWidget(box, 0, Qt.AlignHCenter)
        name = QLabel(dev["n"])
        name.setObjectName("devName")
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignHCenter)
        v.addWidget(name)
        sys_ = QLabel(dev.get("system", ""))
        sys_.setObjectName("devSys")
        sys_.setWordWrap(True)
        sys_.setAlignment(Qt.AlignHCenter)
        v.addWidget(sys_)
        # 默认设备已无 obd 字段（对齐设计稿 .dev-card 两行：name+sub）；有值才显示，
        # 避免整行空标签把卡片撑高。
        if dev.get("obd"):
            obd = QLabel(dev["obd"])
            obd.setObjectName("devObd")
            obd.setWordWrap(True)
            obd.setAlignment(Qt.AlignHCenter)
            v.addWidget(obd)
        # 删除 ×：不参与布局，右上角悬浮（设计 .del-btn absolute）
        del_btn = QPushButton("×")
        del_btn.setObjectName("devDel")    # 22x22 由 theme.qss min/max 约束
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setToolTip("删除设备")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._dev["id"]))
        del_btn.setParent(self)
        self._del_btn = del_btn

    def resizeEvent(self, event):
        super().resizeEvent(event)
        d = getattr(self, "_del_btn", None)
        if d is not None:
            d.setGeometry(self.width() - 22 - 8, 6, 22, 22)

    @property
    def device(self) -> dict:
        return self._dev

    def set_selected(self, sel: bool):
        _prop(self, "sel", "on" if sel else "off")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._dev["id"])
        super().mousePressEvent(event)


class Toast(QLabel):
    """底部居中提示：show_message(msg, kind="ok"|"crit")。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.hide()

    def show_message(self, msg: str, kind: str = "ok"):
        self.setText(msg)
        _prop(self, "kind", kind)
        self.adjustSize()
        self.show()
        self.raise_()
