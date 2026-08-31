"""
LCS700 页面基类：滚动页 + 通用工具。
"""

from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

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
