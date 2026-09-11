"""系统设置页：SETTINGS 11 项渲染；主题切换真实生效，其余演示。"""

from PySide6.QtCore import Qt, Signal, QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox
import platform
from pathlib import Path
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
        self._prefs = QSettings("AutoDrive", "AutoDrive")
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
        desc = QLabel("显示偏好；单位换算尚未接入，诊断数据保留原始单位" if item["n"] == "单位制" else item["d"])
        desc.setWordWrap(True)
        desc.setObjectName("setDesc")
        v.addWidget(desc)
        h.addLayout(v, 1)
        ctrl = self._control(item)
        h.addWidget(ctrl, 0, Qt.AlignVCenter)
        return row

    def _control(self, item):
        typ = item["type"]
        name = item["n"]
        system_pages = {"电源管理": "powersleep", "屏幕亮度": "display", "系统音量": "sound"}
        if name in system_pages:
            b = QPushButton("打开 Windows 设置")
            b.setObjectName("setVal")
            b.clicked.connect(lambda: self._open_system(system_pages[name]))
            return b
        if name in ("字体大小", "单位制"):
            return self._preference_segments(item)
        unsupported = {"语言": "简体中文（其他语言尚未提供）", "数据自动上传": "未配置云同步服务"}
        if name in unsupported:
            b = QPushButton(unsupported[name])
            b.setObjectName("setVal")
            b.setEnabled(False)
            b.setToolTip(unsupported[name])
            return b
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
            b = QComboBox()
            b.addItems(item["options"])
            b.setCurrentText(self._prefs.value("preferences/" + name, item["cur"]))
            b.setObjectName("setVal")
            b.setCursor(Qt.PointingHandCursor)
            b.currentTextChanged.connect(lambda value: self._save_preference(name, value))
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

    def _preference_segments(self, item):
        wrap = QFrame()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        name = item["n"]
        current = self._prefs.value("preferences/" + name, item["cur"])
        buttons = []

        def choose(value):
            for option, button in buttons:
                button.setChecked(option == value)
                _prop(button, "sel", "on" if option == value else "off")
            self._save_preference(name, value)

        for option in item["options"]:
            label = option.split(" (")[0] if name == "单位制" else option
            button = QPushButton(label)
            button.setObjectName("segBtn")
            button.setCheckable(True)
            button.setChecked(option == current)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(option)
            _prop(button, "sel", "on" if option == current else "off")
            button.clicked.connect(lambda checked=False, value=option: choose(value))
            buttons.append((option, button))
            layout.addWidget(button)
        return wrap

    def _do_action(self, item):
        if item.get("action") == "clearCache":
            self._modal("清除缓存", "仅清理 data/cache 下的普通缓存文件，保留报告和配置。", on_ok=self._clear_cache)
        else:
            self._toast("演示功能")

    def _about_modal(self):
        self._modal("关于设备",
                    f"远驰科技 · 智能诊断平台\n系统：{platform.system()} {platform.release()}\nPython：{platform.python_version()}\n设备：{platform.node()}")

    def _open_system(self, page):
        if not QDesktopServices.openUrl(QUrl("ms-settings:" + page)):
            self._toast("无法打开 Windows 设置，请从开始菜单打开", "error")

    def _save_preference(self, name, value):
        self._prefs.setValue("preferences/" + name, value)
        self._prefs.sync()
        if name == "字体大小":
            from ui.theme import ThemeManager
            ThemeManager.instance().apply()
        if name == "单位制":
            self._toast("单位偏好已保存；当前诊断数据仍使用原始单位")
        else:
            self._toast("已保存" + ("，下次启动生效" if name == "启动界面" else ""))

    def _clear_cache(self):
        from config.settings import settings
        root = (Path(settings.data_dir) / "cache").resolve()
        count = 0
        size = 0
        try:
            if root.exists():
                for path in root.rglob("*"):
                    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                        continue
                    length = path.stat().st_size
                    path.unlink()
                    size += length
                    count += 1
            self._toast(f"已清理 {count} 个缓存文件，释放 {size / 1048576:.2f} MB")
        except OSError as exc:
            self._toast(f"部分缓存未清理：{exc}", "error")

    def on_enter(self):
        from ui.theme import ThemeManager
        self.set_current_theme(ThemeManager.instance().resolved)

    def _pick_theme(self, mode):
        self.set_current_theme(mode)
        self.theme_requested.emit(mode)

    def set_current_theme(self, mode: str):
        self._theme = mode
        for m, b in self._theme_btns:
            _prop(b, "sel", "on" if m == mode else "off")
