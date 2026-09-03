"""
LCS700 应用外壳：顶部栏 + 页面栈 + 底部栏 + Toast + 模态框。

  AppShell（QWidget）——
    TBar：RunchLogo + 远驰科技/Runch Tech（点击回首页）+ 页标题胶囊 + CN 胶囊 + 时钟 + 主题 + 红色退出
    QStackedWidget（PAGE_ORDER 19 页）
    BBar：左=账户按钮（头像 LX + 李翔） 右=上下文按钮动态重建（PAGE_CFG）

导航：goPage(page_id) 切页 + 重建标题胶囊 + 重建底栏按钮 + 调用该页 on_enter() 钩子。
动作：底栏按钮 act → nav_requested(action_id, current_page) → MainWindow 分发。
"""

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF, Qt, QTime, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ui.lcsdata import ACCOUNT, PAGE_CFG
from ui.widgets import ClickFrame, RunchLogo, Toast, _fade_in, _prop, _slide_up

__all__ = ["BtnSpec", "PageSpec", "AppShell", "PAGE_ORDER", "PAGE_SPECS"]

# 19 页导航顺序（对应 HTML PAGE_CFG + ai-diagn）
PAGE_ORDER = [
    "home", "ai-diagn", "report", "settings", "account",
    "remote", "remote-ctrl", "remote-invite",
    "special", "advanced", "ebs", "ebs-func", "ebs-info",
    "ebs-dtc", "ebs-dataflow", "ebs-test", "ebs-match", "can", "update",
]


@dataclass
class BtnSpec:
    label: str
    to: str = ""            # target page id → goPage
    act: str = ""           # action id → nav_requested
    cls: str = ""           # "" 普通 | "primary" 渐变主按钮


@dataclass
class PageSpec:
    id: str
    title: str = ""
    btns: list = field(default_factory=list)


def _build_page_specs() -> dict:
    specs = {}
    for pid, cfg in PAGE_CFG.items():
        btns = [BtnSpec(label=b.get("label", ""), to=b.get("to", ""),
                        act=b.get("act", ""), cls=b.get("cls", ""))
                for b in cfg.get("btns", [])]
        specs[pid] = PageSpec(id=pid, title=cfg.get("title", "") or "", btns=btns)
    return specs


PAGE_SPECS: dict = _build_page_specs()


class AppShell(QWidget):
    """应用外壳：顶栏 + 页面栈 + 底栏。页面由 wizard 注册后导航。"""

    nav_requested = Signal(str, str)   # (action_id, current_page_id)
    page_changed = Signal(str)         # page_id
    exit_requested = Signal()          # 退出按钮 → wizard 确认弹窗

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppShell")
        self._pages: dict[str, QWidget] = {}
        self._current = ""
        self._page_resolver = None
        self._build_ui()
        self._clock_on = True
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    # ── UI 构建 ─────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        root.addWidget(self._build_bottombar())

        # Toast（底栏上方居中）
        self._toast = Toast(self)
        self._toast.hide()
        # 模态覆盖层
        self._scrim = QFrame(self)
        self._scrim.setObjectName("ModalScrim")
        self._scrim.setStyleSheet("")
        self._scrim.hide()
        self._scrim_lay = QVBoxLayout(self._scrim)
        self._scrim_lay.setAlignment(Qt.AlignCenter)
        self._modal = None

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TBar")
        bar.setFixedHeight(58)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(10)
        # 品牌区（点击回首页，对齐设计稿 data-go="home"）。
        # ClickFrame：QPushButton 的 sizeHint 忽略内部 layout，会压塌 logo/文字。
        brand = ClickFrame()
        brand.setObjectName("BrandBtn")
        brand.clicked.connect(lambda: self.goPage("home"))
        bh = QHBoxLayout(brand)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(10)
        bh.addWidget(RunchLogo(size=34))
        bv = QVBoxLayout()
        bv.setSpacing(0)
        cn = QLabel("远驰科技")
        cn.setObjectName("BrandCn")
        en = QLabel("Runch Tech")
        en.setObjectName("BrandEn")
        bv.addWidget(cn)
        bv.addWidget(en)
        bh.addLayout(bv)
        h.addWidget(brand, 0, Qt.AlignVCenter)
        h.addSpacing(6)
        self._title_pill = QLabel("")
        self._title_pill.setObjectName("PageTitlePill")
        h.addWidget(self._title_pill, 0, Qt.AlignVCenter)
        h.addStretch(1)
        cn_pill = QLabel("CN · LC20260828")
        cn_pill.setObjectName("CnPill")
        h.addWidget(cn_pill, 0, Qt.AlignVCenter)
        self._clock_pill = QLabel("")
        self._clock_pill.setObjectName("ClockPill")
        h.addWidget(self._clock_pill, 0, Qt.AlignVCenter)
        theme_btn = QPushButton("◐")
        theme_btn.setObjectName("ThemeBtn")
        theme_btn.setCursor(Qt.PointingHandCursor)
        theme_btn.setToolTip("切换深色/浅色")
        theme_btn.clicked.connect(self._toggle_theme)
        h.addWidget(theme_btn, 0, Qt.AlignVCenter)
        exit_btn = QPushButton("退出")
        exit_btn.setObjectName("ExitBtn")
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.clicked.connect(self.exit_requested.emit)
        h.addWidget(exit_btn, 0, Qt.AlignVCenter)
        # 兼容引用：设备状态不显示，对象保留以便 wizard 流程 setText 与测试断言仍可用。
        self._dev_status = QLabel("○ 就绪")
        self._dev_status.setObjectName("DevStatus")
        self._dev_status.hide()
        return bar

    def _build_bottombar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("BBar")
        bar.setFixedHeight(62)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(8)
        acc = ClickFrame()
        acc.setObjectName("AccountBtn")
        acc.clicked.connect(lambda: self.goPage("account"))
        ah = QHBoxLayout(acc)
        ah.setContentsMargins(6, 4, 10, 4)
        ah.setSpacing(8)
        avatar = QLabel(ACCOUNT["avatar"])
        avatar.setObjectName("AvatarLabel")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        ah.addWidget(avatar, 0, Qt.AlignVCenter)
        name = QLabel(ACCOUNT["name"])
        name.setObjectName("AccountName")
        ah.addWidget(name, 0, Qt.AlignVCenter)
        h.addWidget(acc, 0, Qt.AlignVCenter)
        h.addStretch(1)
        self._bb_right = QHBoxLayout()
        self._bb_right.setSpacing(8)
        h.addLayout(self._bb_right)
        return bar

    # ── 时钟 ───────────────────────────────────

    def _tick_clock(self):
        if self._clock_on:
            now = QTime.currentTime()
            self._clock_pill.setText(now.toString("HH:mm:ss"))

    def set_clock_enabled(self, on: bool):
        self._clock_on = on
        self._clock_pill.setVisible(on)

    def _toggle_theme(self):
        from ui.theme import ThemeManager

        tm = ThemeManager.instance()
        if tm is None:
            return
        tm.set_theme("light" if tm.resolved == "dark" else "dark")

    # ── 页面注册 / 导航 ────────────────────────

    def add_pages(self, pages: dict):
        for pid in PAGE_ORDER:
            if pid in pages:
                self._pages[pid] = pages[pid]
                self.stack.addWidget(pages[pid])

    def set_page_resolver(self, resolver):
        """懒加载：goPage 遇到未构建页面时调用 resolver(page_id) → 页面实例。"""
        self._page_resolver = resolver

    def goPage(self, page_id: str):
        first = (self._current == "")
        # 未构建的页（懒加载）：交给 resolver 构建后再入栈
        if self._pages.get(page_id) is None:
            if self._page_resolver is None or page_id not in PAGE_ORDER:
                return
            page = self._page_resolver(page_id)
            if page is None:
                return
            self._pages[page_id] = page
            self.stack.addWidget(page)
        # 离开上一页：让旧页停掉后台定时器等
        if self._current and self._current != page_id:
            prev = self._pages.get(self._current)
            hook = getattr(prev, "on_leave", None)
            if callable(hook):
                hook()
        self.stack.setCurrentWidget(self._pages[page_id])
        self._current = page_id
        if not first:
            _fade_in(self._pages[page_id], 150)   # 首次进入（启动即主页）保持即时，后续切页轻淡入
        self._rebuild_title()
        self._rebuild_bb()
        page = self._pages[page_id]
        hook = getattr(page, "on_enter", None)
        if callable(hook):
            hook()
        self.page_changed.emit(page_id)

    def current_page(self) -> str:
        return self._current

    def _rebuild_title(self):
        spec = PAGE_SPECS.get(self._current)
        title = spec.title if spec else ""
        self._title_pill.setText(title)
        self._title_pill.setVisible(bool(title))

    def _rebuild_bb(self):
        # 清空右侧按钮（先脱离父子树再 deleteLater，避免泄漏到 findChildren）
        while self._bb_right.count():
            item = self._bb_right.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        spec = PAGE_SPECS.get(self._current)
        for btn in (spec.btns if spec else []):
            b = QPushButton(btn.label)
            b.setObjectName("bbBtn")
            _prop(b, "bb", "primary" if btn.cls == "primary" else "")
            b.setCursor(Qt.PointingHandCursor)
            if btn.to:
                b.clicked.connect(lambda _=False, to=btn.to: self.goPage(to))
            elif btn.act:
                b.clicked.connect(lambda _=False, act=btn.act: self.nav_requested.emit(act, self._current))
            self._bb_right.addWidget(b, 0, Qt.AlignVCenter)

    # ── 设备状态 / Toast / 模态 ─────────────────

    def set_status(self, text: str):
        self._dev_status.setText(text)

    def toast(self, msg: str, kind: str = "ok"):
        self._toast.show_message(msg, kind)
        # 定位：底栏上方居中
        self._toast.adjustSize()
        self._toast.move((self.width() - self._toast.width()) // 2,
                         self.height() - 62 - self._toast.height() - 24)
        _slide_up(self._toast)
        QTimer.singleShot(2600, self._toast.hide)

    def show_modal(self, title, body="", ok_text="确定", cancel_text="取消", on_ok=None, content=None):
        self._scrim.setGeometry(self.rect())
        self._scrim.show()
        self._scrim.raise_()
        _fade_in(self._scrim, 160)       # 遮罩淡入（含其内模态卡）
        card = QFrame(self._scrim)
        card.setObjectName("Modal")
        card.setFixedWidth(380)
        v = QVBoxLayout(card)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(12)
        t = QLabel(title)
        t.setObjectName("ModalTitle")
        t.setWordWrap(True)
        v.addWidget(t)
        if body:
            b = QLabel(body)
            b.setObjectName("ModalBody")
            b.setWordWrap(True)
            v.addWidget(b)
        if content is not None:
            v.addWidget(content)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch(1)
        if cancel_text:
            cancel = QPushButton(cancel_text)
            cancel.setProperty("role", "ghost")
            cancel.setCursor(Qt.PointingHandCursor)
            cancel.clicked.connect(self.close_modal)
            btns.addWidget(cancel)
        if ok_text:
            ok = QPushButton(ok_text)
            ok.setProperty("role", "primary")
            ok.setCursor(Qt.PointingHandCursor)

            def _on_ok():
                self.close_modal()
                if on_ok:
                    on_ok()
            ok.clicked.connect(_on_ok)
            btns.addWidget(ok)
        v.addLayout(btns)
        self._modal = card
        self._scrim_lay.addWidget(card)

    def close_modal(self):
        if self._modal is not None:
            self._modal.deleteLater()
            self._modal = None
        self._scrim.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scrim.setGeometry(self.rect())
        if self._toast.isVisible():
            self._toast.move((self.width() - self._toast.width()) // 2,
                             self.height() - 62 - self._toast.height() - 24)
