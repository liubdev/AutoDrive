"""远程协助：入口 tiles + 远程控制对方（三步 + ID + 九宫格）+ 邀请对方控制。"""

import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from ui.lcsdata import REMOTE_CTRL_STEPS
from ui.pages.base import LcsPage
from ui.widgets import _prop

__all__ = ["RemotePage", "RemoteCtrlPage", "RemoteInvitePage"]


class _Tile(QFrame):
    def __init__(self, key, title, desc, on_tap, parent=None):
        super().__init__(parent)
        _prop(self, "card", "remote-tile")
        self._key = key
        self._on_tap = on_tap      # 导航回调（RemotePage._go，走已注入的 shell）
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)
        t = QLabel(title)
        t.setObjectName("rtName")
        v.addWidget(t)
        d = QLabel(desc)
        d.setObjectName("rtDesc")
        d.setWordWrap(True)
        v.addWidget(d)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._key:
            self._on_tap(self._key)
        super().mousePressEvent(event)


class RemotePage(LcsPage):
    PAGE_ID = "remote"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        t = QLabel("远程协助")
        t.setObjectName("homeTitle")
        self._add(t)
        sub = QLabel("连接对端设备，进行远程控制或被远程协助")
        sub.setObjectName("homeSub")
        self._add(sub)
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.addWidget(_Tile("remote-ctrl", "远程控制对方设备", "输入对方设备 ID，请求控制权", self._go), 0, 0)
        grid.addWidget(_Tile("remote-invite", "邀请对方控制我的设备", "生成我的 ID，等待对方连接", self._go), 0, 1)
        for c in (0, 1):
            grid.setColumnStretch(c, 1)
        self._add_layout(grid)


class RemoteCtrlPage(LcsPage):
    PAGE_ID = "remote-ctrl"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        t = QLabel("远程控制对方设备")
        t.setObjectName("homeTitle")
        self._add(t)
        row = QHBoxLayout()
        row.setSpacing(16)
        # 左侧三步说明
        left = QVBoxLayout()
        left.setSpacing(10)
        for title, body in REMOTE_CTRL_STEPS:
            s = QLabel(f"<b>{title}</b>　{body}")
            s.setObjectName("rtStep")
            s.setWordWrap(True)
            left.addWidget(s)
        row.addLayout(left, 3)
        # 右侧：ID 输入 + 九宫格
        right = QFrame()
        _prop(right, "card", "remote-tile")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(10)
        lbl = QLabel("请输入对方设备的 ID")
        lbl.setObjectName("SecTitle")
        rv.addWidget(lbl)
        id_row = QHBoxLayout()
        id_row.setSpacing(8)
        self._id_input = QLineEdit()
        self._id_input.setObjectName("remoteIdInput")
        self._id_input.setMaxLength(9)
        self._id_input.setPlaceholderText("请输入设备 ID")
        self._id_input.setCursor(Qt.IBeamCursor)
        self._id_input.returnPressed.connect(self._connect)
        id_row.addWidget(self._id_input, 1)
        connect = QPushButton("连接对方")
        connect.setProperty("role", "primary")
        connect.setCursor(Qt.PointingHandCursor)
        connect.clicked.connect(self._connect)
        id_row.addWidget(connect)
        rv.addLayout(id_row)
        pad = QFrame()
        pad.setObjectName("keypad")
        pg = QGridLayout(pad)
        pg.setSpacing(8)
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
        for i, k in enumerate(keys):
            b = QPushButton(k)
            b.setFixedSize(56, 46)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, d=k: self._press(d))
            pg.addWidget(b, i // 3, i % 3)
        del_btn = QPushButton("删除")
        del_btn.setFixedSize(120, 46)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self._backspace)
        pg.addWidget(del_btn, 3, 1, 1, 2)
        rv.addWidget(pad)
        row.addWidget(right, 2)
        self._add_layout(row)

    def _press(self, d):
        if len(self._id_input.text()) < 9:
            self._id_input.setText(self._id_input.text() + d)

    def _backspace(self):
        self._id_input.setText(self._id_input.text()[:-1])

    def _connect(self):
        if len(self._id_input.text()) < 9:
            self._toast("请输入 9 位对端 ID", "crit")
            return
        self._modal("正在连接…", f"正在连接对方设备 {self._id_input.text()}，请对方确认…",
                    ok_text="", cancel_text="关闭")
        QTimer.singleShot(2000, lambda: self._connected())

    def _connected(self):
        self.shell.close_modal()
        self._toast("连接成功（演示）")


class RemoteInvitePage(LcsPage):
    PAGE_ID = "remote-invite"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        t = QLabel("邀请对方控制我的设备")
        t.setObjectName("homeTitle")
        self._add(t)
        sub = QLabel("将下方 ID 告知对方，对方连接后将发起控制请求")
        sub.setObjectName("homeSub")
        self._add(sub)
        card = QFrame()
        _prop(card, "card", "remote-tile")
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)
        lbl = QLabel("请将以下 ID 告诉您的邀请对象")
        lbl.setObjectName("SecTitle")
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        self._id_lbl = QLabel("")
        self._id_lbl.setObjectName("remoteBigId")
        self._id_lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(self._id_lbl)
        act = QHBoxLayout()
        act.addStretch(1)
        react = QPushButton("重新激活")
        react.setProperty("role", "ghost")
        react.setCursor(Qt.PointingHandCursor)
        react.clicked.connect(self._reactivate)
        act.addWidget(react)
        cancel = QPushButton("取消远程连接")
        cancel.setProperty("role", "ghost")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(lambda: self._go("remote"))
        act.addWidget(cancel)
        act.addStretch(1)
        v.addLayout(act)
        # 注意说明（对齐设计稿 .notes）
        notes = QFrame()
        _prop(notes, "card", "notes")
        nv = QVBoxLayout(notes)
        nv.setContentsMargins(16, 12, 16, 12)
        nv.setSpacing(4)
        nt = QLabel("注意")
        nt.setObjectName("notesTitle")
        nv.addWidget(nt)
        nb = QLabel("1. 对方需确认授权，否则无法连接。\n"
                    "2. 如长时间未连接成功，请点击「重新激活」再次等待对方连接。")
        nb.setObjectName("notesBody")
        nb.setWordWrap(True)
        nv.addWidget(nb)
        v.addWidget(notes)
        self._add(card)
        self._reactivate()

    def _reactivate(self):
        digits = "".join(str(random.randint(0, 9)) for _ in range(9))
        self._id_lbl.setText(f"{digits[:3]}-{digits[3:6]}-{digits[6:]}")
        self._toast("已重新激活连接 ID")
