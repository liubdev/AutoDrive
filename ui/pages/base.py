"""
LCS700 页面基类：滚动页 + 通用工具。
"""

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from ui.theme import ThemeManager
from ui.widgets import _prop, section_header  # noqa: F401  重新导出

__all__ = ["LcsPage", "_prop", "section_header"]


class LcsPage(QWidget):
    """带滚动内容的页面基类。shell 由 wizard 注入（self.shell）。"""

    PAGE_ID = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        if self.PAGE_ID:
            self.setObjectName(f"page-{self.PAGE_ID}")
        self.shell = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(24, 20, 24, 28)
        self._body.setSpacing(16)
        self._scroll.setWidget(body)
        lay.addWidget(self._scroll)

    def paintEvent(self, event):
        """对齐 HTML body 背景：底色 + 顶部径向光 + 40px 细网格。"""
        super().paintEvent(event)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self._tok("board", "#0b0e14")))
        grad = QRadialGradient(QPointF(self.width() / 2, 0), max(self.width(), 1) * 0.55)
        if self._mode() == "light":
            glow = QColor(56, 189, 248, 18)
            grid = None
        else:
            glow = QColor(45, 62, 80, 90)
            grid = QColor(255, 255, 255, 8)
        grad.setColorAt(0.0, glow)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), grad)
        if grid is not None:
            p.setPen(grid)
            for x in range(0, self.width(), 40):
                p.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), 40):
                p.drawLine(0, y, self.width(), y)

    def _mode(self) -> str:
        tm = ThemeManager.instance()
        return tm.resolved if tm is not None else "dark"

    def _tok(self, key: str, fallback: str) -> str:
        tm = ThemeManager.instance()
        return tm.tokens.get(key, fallback) if tm is not None else fallback

    def on_enter(self):
        """切页到此页时由 AppShell 调用。"""

    def on_leave(self):
        """切页离开此页时由 AppShell 调用（用于停后台定时器等）。"""

    def _add(self, widget):
        self._body.addWidget(widget)

    def _add_layout(self, layout):
        self._body.addLayout(layout)

    def _add_stretch(self):
        self._body.addStretch(1)

    # ── 便捷：toast / 模态 / 导航 ────────────────

    def _toast(self, msg, kind="ok"):
        if self.shell is not None:
            self.shell.toast(msg, kind)

    def _go(self, page_id):
        if self.shell is not None:
            self.shell.goPage(page_id)

    def _modal(self, title, body="", ok_text="确定", cancel_text="取消", on_ok=None, content=None):
        if self.shell is not None:
            self.shell.show_modal(title, body, ok_text=ok_text, cancel_text=cancel_text,
                                  on_ok=on_ok, content=content)
