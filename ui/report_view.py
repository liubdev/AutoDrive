"""Diagnosis results with an optional, lazily loaded HTML reference manual."""

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

logger = logging.getLogger("autodrive.ui.report_view")


def manual_path() -> Path:
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent / "ui"
    else:
        root = Path(__file__).resolve().parent
    return root / "assets" / "manuals" / "md1cs089_v6.html"


class ManualView(QWidget):
    """Read the bundled reference document without changing diagnosis data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None
        self._started = False
        self._loading = False
        self._zoom = 1.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        note = QLabel("MD1CS089 参考手册 · 原版 V6；内容为参考资料，并非本次车辆的诊断结论。")
        note.setObjectName("SecHint")
        note.setWordWrap(True)
        layout.addWidget(note)

        toolbar = QHBoxLayout()
        self._status = QLabel("首次打开时加载手册")
        self._status.setObjectName("SecHint")
        self._status.setWordWrap(True)
        toolbar.addWidget(self._status, 1)
        self._zoom_out = self._button("缩小", lambda: self._set_zoom(self._zoom - 0.1))
        self._zoom_reset = self._button("100%", lambda: self._set_zoom(1.0))
        self._zoom_in = self._button("放大", lambda: self._set_zoom(self._zoom + 0.1))
        for button in (self._zoom_out, self._zoom_reset, self._zoom_in):
            button.setEnabled(False)
            toolbar.addWidget(button)
        self._retry = self._button("重新加载", self.load_manual)
        toolbar.addWidget(self._retry)
        layout.addLayout(toolbar)

        self._content = QVBoxLayout()
        layout.addLayout(self._content)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(30000)
        self._timeout.timeout.connect(self._load_timed_out)

    @staticmethod
    def _button(text, action):
        button = QPushButton(text)
        button.setProperty("role", "mini")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(action)
        return button

    def ensure_loaded(self):
        if not self._started:
            self.load_manual()

    def load_manual(self):
        self._started = True
        path = manual_path()
        if not path.is_file():
            self._fail("手册文件缺失，请修复安装后重试。")
            logger.error("Reference manual missing: %s", path)
            return
        if self._view is None:
            try:
                # Import only when requested: Chromium should not delay login or diagnosis.
                from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
                from PySide6.QtWebEngineWidgets import QWebEngineView

                class ManualPage(QWebEnginePage):
                    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
                        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == path.resolve()

                self._view = QWebEngineView(self)
                page = ManualPage(self._view)
                self._view.setPage(page)
                for attribute in (
                    QWebEngineSettings.WebAttribute.JavascriptEnabled,
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
                ):
                    page.settings().setAttribute(attribute, False)
                self._view.setContextMenuPolicy(Qt.NoContextMenu)
                self._view.setMinimumWidth(0)
                self._view.setFixedHeight(620)
                self._view.loadFinished.connect(self._load_finished)
                page.renderProcessTerminated.connect(self._render_failed)
                self._content.addWidget(self._view)
            except (ImportError, OSError, RuntimeError):
                logger.exception("Cannot initialize HTML manual viewer")
                if self._view is not None:
                    self._view.deleteLater()
                    self._view = None
                self._fail("无法启动手册阅读器，请检查安装是否完整后重试。")
                return
        self._loading = True
        self._status.setText("正在加载手册…")
        self._retry.setEnabled(False)
        self._view.hide()
        self._timeout.start()
        self._view.load(QUrl.fromLocalFile(str(path.resolve())))

    def _load_finished(self, ok):
        if not self._loading:
            return
        self._loading = False
        self._timeout.stop()
        if not ok:
            self._fail("手册加载失败，请点击重新加载。")
            logger.warning("Reference manual failed to load")
            return
        self._status.setText("参考手册 · 可滚动阅读、选中文字复制")
        self._retry.setEnabled(True)
        self._view.show()
        self._zoom_reset.setEnabled(True)
        self._set_zoom(self._zoom)

    def _load_timed_out(self):
        self._loading = False
        if self._view is not None:
            self._view.stop()
        self._fail("手册加载超时，请点击重新加载。")

    def _render_failed(self, status, exit_code):
        logger.error("HTML renderer exited: %s (%s)", status, exit_code)
        self._fail("手册阅读器已停止，请点击重新加载。")

    def _fail(self, message):
        self._loading = False
        self._timeout.stop()
        self._status.setText(message)
        self._retry.setEnabled(True)
        if self._view is not None:
            self._view.hide()
        for button in (self._zoom_out, self._zoom_reset, self._zoom_in):
            button.setEnabled(False)

    def _set_zoom(self, value):
        self._zoom = round(max(0.6, min(1.6, value)), 1)
        if self._view is not None:
            self._view.setZoomFactor(self._zoom)
        self._zoom_reset.setText(f"{self._zoom:.0%}")
        self._zoom_out.setEnabled(self._zoom > 0.6)
        self._zoom_in.setEnabled(self._zoom < 1.6)


class ReportViews(QWidget):
    """Use hidden widgets so a long result does not dictate the manual's height."""

    def __init__(self, result_widget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._buttons = QButtonGroup(self)
        for index, title in enumerate(("诊断结果", "排查手册")):
            button = QPushButton(title)
            button.setProperty("role", "report-tab")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self._buttons.addButton(button, index)
            tabs.addWidget(button)
        tabs.addStretch(1)
        layout.addLayout(tabs)
        self._result = result_widget
        self._manual = ManualView(self)
        layout.addWidget(self._result)
        layout.addWidget(self._manual)
        self._buttons.idClicked.connect(self._select)
        self.show_result()

    def show_result(self):
        self._select(0)

    def _select(self, index):
        self._buttons.button(index).setChecked(True)
        self._result.setVisible(index == 0)
        self._manual.setVisible(index == 1)
        if index == 1:
            self._manual.ensure_loaded()
