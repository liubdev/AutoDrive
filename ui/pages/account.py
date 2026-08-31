"""账户页：账户信息卡 + 授权统计卡 + 退出登录（对齐 docs/RunchTech_V01.html）。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.lcsdata import ACCOUNT
from ui.pages.base import LcsPage
from ui.widgets import _prop

__all__ = ["AccountPage"]

# 账户行（对齐设计稿 .account-line）：中文标签 → 数据键
_META = [("手机号", "phone"), ("邮箱", "email"), ("账号编号", "no"),
         ("所在门店", "shop"), ("注册时间", "reg")]


class AccountPage(LcsPage):
    PAGE_ID = "account"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        wrap = QHBoxLayout()
        wrap.setSpacing(16)

        # ── 左：账户信息卡 ──
        left = QFrame()
        _prop(left, "card", "account")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 18, 20, 18)
        lv.setSpacing(0)

        t1 = QLabel("账户信息")
        t1.setObjectName("panelTitle")
        lv.addWidget(t1)
        lv.addSpacing(8)

        # 头像 + 姓名 / 角色
        avatar_row = QFrame()
        _prop(avatar_row, "card", "acc-line")
        ah = QHBoxLayout(avatar_row)
        ah.setContentsMargins(0, 14, 0, 14)
        ah.setSpacing(16)
        avatar = QLabel(ACCOUNT["avatar"])
        avatar.setObjectName("AvatarBig")
        avatar.setFixedSize(64, 64)
        avatar.setAlignment(Qt.AlignCenter)
        ah.addWidget(avatar)
        hv = QVBoxLayout()
        name = QLabel(ACCOUNT["name"])
        name.setObjectName("accName")
        hv.addWidget(name)
        role = QLabel(ACCOUNT["role"])
        role.setObjectName("accRole")
        hv.addWidget(role)
        ah.addLayout(hv)
        ah.addStretch(1)
        lv.addWidget(avatar_row)

        # 账户行（手机号 / 邮箱 / 账号编号 / 所在门店 / 注册时间）
        for i, (label, key) in enumerate(_META):
            row = QFrame()
            _prop(row, "card", "acc-line" if i < len(_META) - 1 else "acc-line-end")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 11, 0, 11)
            kk = QLabel(label)
            kk.setObjectName("accMetaK")
            kk.setFixedWidth(72)
            vv = QLabel(ACCOUNT[key])
            vv.setObjectName("accMetaV")
            rh.addWidget(kk)
            rh.addWidget(vv)
            rh.addStretch(1)
            lv.addWidget(row)
        lv.addStretch(1)
        wrap.addWidget(left, 6)

        # ── 右：授权与统计卡 ──
        right = QFrame()
        _prop(right, "card", "account")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(20, 18, 20, 18)
        rv.setSpacing(0)

        t2 = QLabel("授权与统计")
        t2.setObjectName("panelTitle")
        rv.addWidget(t2)
        rv.addSpacing(8)

        for k, val, st in ACCOUNT["stat"]:
            row = QFrame()
            _prop(row, "card", "stat-panel")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(14, 10, 14, 10)
            kk = QLabel(k)
            kk.setObjectName("statRK")
            vv = QLabel(val)
            vv.setObjectName("statRV")
            _prop(vv, "st", st)
            rh.addWidget(kk)
            rh.addWidget(vv, 1, Qt.AlignRight)
            rv.addWidget(row)
            rv.addSpacing(6)
        rv.addSpacing(6)

        logout = QPushButton("退出登录")
        logout.setProperty("role", "danger")
        logout.setMinimumHeight(40)
        logout.setCursor(Qt.PointingHandCursor)
        logout.clicked.connect(self._confirm_logout)
        rv.addWidget(logout)
        rv.addStretch(1)
        wrap.addWidget(right, 5)

        self._add_layout(wrap)

    def _confirm_logout(self):
        self._modal("退出登录", "退出后将清除当前登录状态，确定继续？",
                    ok_text="退出", on_ok=lambda: self._toast("已退出（演示）"))
