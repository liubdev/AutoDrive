"""
AutoDrive 品牌 Logo：仪表盘（speedometer）造型。

启动页（进度动画）与主页（静态）共用。
progress 0~1 控制扫过的弧长与指针位置；1 为完整状态。
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_RING = "#DDE5EE"      # 外圈底色
_ACC = "#0D9488"       # 强调（浅色主题 teal）
_ACC_SOFT = "#7FD8CC"
_NEEDLE = "#17213A"    # 指针深色
_TICK = "#B9C4D4"

_SWEEP_START = 200.0    # 弧起始角（0°=右, 270°=上）
_SWEEP_SPAN = 140.0     # 弧跨度（顶部 140°）


class LogoWidget(QWidget):
    def __init__(self, progress: float = 1.0, size: int = 96, parent=None):
        super().__init__(parent)
        self._progress = max(0.0, min(1.0, progress))
        if size:
            self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def setProgress(self, p: float):
        self._progress = max(0.0, min(1.0, p))
        self.update()

    def progress(self) -> float:
        return self._progress

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        r = min(w, h) / 2 - 5

        # 外圈
        pen = QPen(QColor(_RING), 8)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, r, r)

        # 刻度
        pen = QPen(QColor(_TICK), 2)
        pen.setCapStyle(Qt.RoundCap)
        for i in range(5):
            a = math.radians(_SWEEP_START + _SWEEP_SPAN / 4 * i)
            x1 = c.x() + (r - 16) * math.cos(a)
            y1 = c.y() + (r - 16) * math.sin(a)
            x2 = c.x() + (r - 6) * math.cos(a)
            y2 = c.y() + (r - 6) * math.sin(a)
            p.setPen(pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # 扫过弧（进度）
        sweep = _SWEEP_SPAN * self._progress
        if sweep > 0.4:
            arc = QRectF(c.x() - r, c.y() - r, r * 2, r * 2)
            grad_pen = QPen(QColor(_ACC), 8)
            grad_pen.setCapStyle(Qt.RoundCap)
            p.setPen(grad_pen)
            p.drawArc(arc, int(_SWEEP_START * 16), int(sweep * 16))

        # 指针
        a = math.radians(_SWEEP_START + sweep)
        tip_x = c.x() + (r - 14) * math.cos(a)
        tip_y = c.y() + (r - 14) * math.sin(a)
        pen = QPen(QColor(_NEEDLE), 3)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(c, QPointF(tip_x, tip_y))

        # 中心
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(_ACC))
        p.drawEllipse(c, 7, 7)
        p.setBrush(QColor(_ACC_SOFT))
        p.drawEllipse(c, 3, 3)
