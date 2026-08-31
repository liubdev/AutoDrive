"""系统设置页：SETTINGS 11 项渲染；主题切换真实生效，其余演示。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from ui.lcsdata import SETTINGS
from ui.pages.base import LcsPage
from ui.widgets import _prop

__all__ = ["SettingsPage"]


class SettingsPage(LcsPage):
    PAGE_ID = "settings"

    theme_requested = Signal(str)   # "dark" | "light"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme = "dark"
        self._theme_btns = []
        self._build_ui()

    def _build_ui(self):
        t = QLabel("系统设置")
        t.setObjectName("homeTitle")
        self._add(t)
        for item in SETTINGS:
            self._add(self._row(item))

    def _row(self, item) -> QFrame:
        row = QFrame()
        _prop(row, "card", "set-row")
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)
        v = QVBoxLayout()
        v.setSpacing(2)
        name = QLabel(item["n"])
        name.setObjectName("setName")
        v.addWidget(name)
        desc = QLabel(item["d"])
        desc.setObjectName("setDesc")
        v.addWidget(desc)
        h.addLayout(v, 1)
        ctrl = self._control(item)
        h.addWidget(ctrl, 0, Qt.AlignVCenter)
        return row

    def _control(self, item):
        typ = item["type"]
        if typ == "theme":
            wrap = QFrame()
            wh = QHBoxLayout(wrap)
            wh.setContentsMargins(0, 0, 0, 0)
            wh.setSpacing(4)
            for mode, label in (("dark", "深色"), ("light", "浅色")):
                b = QPushButton(label)
                b.setObjectName("segBtn")
                b.setCursor(Qt.PointingHandCursor)
                _prop(b, "sel", "on" if mode == self._theme else "off")
                b.clicked.connect(lambda _=False, m=mode: self._pick_theme(m))
                wh.addWidget(b)
                self._theme_btns.append((mode, b))
            return wrap
        if typ == "select":
            b = QPushButton(item["cur"])
            b.setObjectName("setVal")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=item: self._toast(f"{i['n']}：演示功能，暂不支持修改"))
            return b
        if typ == "slider":
            s = QSlider(Qt.Horizontal)
            s.setObjectName("setSlider")
            s.setRange(item["min"], item["max"])
            s.setValue(item["val"])
            s.setFixedWidth(160)
            s.setEnabled(False)
            return s
        if typ == "toggle":
            wrap = QFrame()
            wh = QHBoxLayout(wrap)
            wh.setContentsMargins(0, 0, 0, 0)
            wh.setSpacing(4)
            for label, val in (("开", True), ("关", False)):
                b = QPushButton(label)
                b.setObjectName("segBtn")
                b.setCursor(Qt.PointingHandCursor)
                _prop(b, "sel", "on" if val == item.get("val") else "off")
                b.clicked.connect(lambda _=False, i=item: self._toast(f"{i['n']}：演示功能"))
                wh.addWidget(b)
            return wrap
        if typ == "action":
            b = QPushButton("立即清理" if item.get("action") == "clearCache" else "立即执行")
            b.setObjectName("setVal")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=item: self._do_action(i))
            return b
        if typ == "about":
            b = QPushButton("v2.4.1 ›")
            b.setObjectName("setVal")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(self._about_modal)
            return b
        return QLabel("")

    def _do_action(self, item):
        if item.get("action") == "clearCache":
            self._toast("已清理 24.6 MB 缓存")
        else:
            self._toast("演示功能")

    def _about_modal(self):
        self._modal("关于设备",
                    "远驰科技 · 智能诊断平台 LCS700\n软件版本 v2.4.1\n序列号 LC20260828-0017\n版权所有 © 2026 远驰科技")

    def _pick_theme(self, mode):
        self.set_current_theme(mode)
        self.theme_requested.emit(mode)

    def set_current_theme(self, mode: str):
        self._theme = mode
        for m, b in self._theme_btns:
            _prop(b, "sel", "on" if m == mode else "off")
