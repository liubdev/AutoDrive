"""骨架占位页：专用诊断仪 / 高级功能 / EBS 子系统 / CAN 扫描。

kind ∈ {grid5, grid4, list, func-menu, info-table, ec-table, match-grid, upd-list}
点击项有 target → goPage；否则 toast「演示功能」。
"""

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QVBoxLayout, QWidget,
)

from ui.lcsdata import (
    ADVANCED_ITEMS, CAN_LIST, EBS_DF, EBS_DTC, EBS_ECU, EBS_FUNCS, EBS_INFO,
    EBS_TEST, IC64, MATCH_GROUPS, SMALL, SPECIAL_ITEMS, UPDATES,
)
from ui.pages.base import LcsPage
from ui.widgets import SvgGlyph, _prop

__all__ = [
    "SkeletonPage", "SpecialPage", "AdvancedPage",
    "EbsEcuPage", "EbsFuncPage", "EbsInfoPage", "EbsDtcPage",
    "EbsDataflowPage", "EbsTestPage", "EbsMatchPage", "CanPage", "UpdatePage",
]


# EBS 数据流动画参数：rpm/喷油等按正弦抖动，其余静态。模块级缓存，避免每 tick 重建。
_DF_BASE = {
    "rpm": 750, "injT": 42.0, "injN": 38.5, "cyl1": 750, "cyl2": 750,
    "cyl3": 750, "cyl4": 750, "engTime": 4820, "ambT": 24, "inT": 28, "batV": 24.6,
}
_DF_AMP = {
    "rpm": 30, "cyl1": 30, "cyl2": 30, "cyl3": 30, "cyl4": 30,
    "injT": 4, "injN": 4, "engTime": 0, "ambT": 0, "inT": 0, "batV": 0.3,
}


class SkeletonPage(LcsPage):
    """按 kind 渲染数据；PAGE_ID / _KIND / _DATA 由子类提供。"""

    _KIND = "list"
    _DATA = []
    _BACK = "home"

    # ec-table 三种页的列配置（对齐设计稿：表头 + 列宽比）
    _EC_CFG = {
        "ebs-dtc": (("故障码", "描述", "状态"), (13, 30, 10)),
        "ebs-dataflow": (("名称", "值", "单位"), (30, 12, 10)),
        "ebs-test": (("测试项目", "状态", "操作"), (30, 12, 12)),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        title = QLabel(self.PAGE_ID)
        title.setObjectName("homeTitle")
        self._add(title)
        # kind 用连字符（ec-table / func-menu…），方法名用下划线（_render_ec_table）
        renderer = getattr(self, f"_render_{self._KIND.replace('-', '_')}", None)
        if renderer:
            renderer(self._DATA)

    # ── 渲染器 ─────────────────────────────────

    def _render_grid5(self, data):
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, item in enumerate(data):
            t = QFrame()
            _prop(t, "card", "grid5")
            t.setCursor(Qt.PointingHandCursor)
            v = QVBoxLayout(t)
            v.setContentsMargins(12, 12, 12, 12)
            v.setSpacing(8)
            # 设计稿 .grid-card .seq：左上角序号徽章
            seq = QLabel(f"{i + 1:02d}")
            seq.setObjectName("gridSeq")
            v.addWidget(seq, 0, Qt.AlignLeft | Qt.AlignTop)
            v.addStretch(1)
            v.addWidget(SvgGlyph(IC64.get(item["ic"], ""), size=50, stroke="acc", viewbox=64),
                        0, Qt.AlignCenter)
            name = QLabel(item["n"])
            name.setObjectName("gridName")
            v.addWidget(name, 0, Qt.AlignCenter)
            sub = QLabel(item.get("sub", ""))
            sub.setObjectName("gridSub")
            v.addWidget(sub, 0, Qt.AlignCenter)
            v.addStretch(1)
            target = item.get("to")
            t.mousePressEvent = lambda _e, to=target, n=item["n"]: self._tap(to, n)
            grid.addWidget(t, i // 5, i % 5)
        for c in range(5):
            grid.setColumnStretch(c, 1)
        self._add_layout(grid)

    def _render_grid4(self, data):
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, item in enumerate(data):
            t = QFrame()
            _prop(t, "card", "grid4")
            t.setCursor(Qt.PointingHandCursor)
            v = QVBoxLayout(t)
            v.setContentsMargins(12, 12, 12, 12)
            v.setSpacing(8)
            seq = QLabel(f"{i + 1:02d}")
            seq.setObjectName("gridSeq")
            v.addWidget(seq, 0, Qt.AlignLeft | Qt.AlignTop)
            v.addStretch(1)
            v.addWidget(SvgGlyph(SMALL.get(item["ic"], ""), size=26, stroke="acc", viewbox=24),
                        0, Qt.AlignCenter)
            name = QLabel(item["n"])
            name.setObjectName("gridName")
            v.addWidget(name, 0, Qt.AlignCenter)
            v.addStretch(1)
            target = item.get("to")
            t.mousePressEvent = lambda _e, to=target, n=item["n"]: self._tap(to, n)
            grid.addWidget(t, i // 4, i % 4)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        self._add_layout(grid)

    def _render_list(self, data):
        for i, row in enumerate(data):
            if isinstance(row, dict):
                name = row.get("n", row.get("name", ""))
                target = row.get("to")
                sub = row.get("d", row.get("sub", ""))
            else:
                name, target, sub = row, None, ""
            r = QFrame()
            r.setObjectName("listRow")
            r.setCursor(Qt.PointingHandCursor)
            h = QHBoxLayout(r)
            h.setContentsMargins(14, 12, 14, 12)
            h.setSpacing(14)
            # 设计稿 .list-row .seq：32px 序号徽章
            seq = QLabel(f"{i + 1:02d}")
            seq.setObjectName("listSeq")
            seq.setFixedSize(32, 32)
            seq.setAlignment(Qt.AlignCenter)
            h.addWidget(seq)
            lbl = QLabel(name)
            lbl.setObjectName("listName")
            h.addWidget(lbl)
            if sub:
                s = QLabel(sub)
                s.setObjectName("listSub")
                h.addWidget(s)
            h.addStretch(1)
            go = QPushButton("›")
            go.setObjectName("listGo")
            go.setFixedSize(26, 26)
            go.setCursor(Qt.PointingHandCursor)
            go.clicked.connect(lambda _=False, to=target, n=name: self._tap(to, n))
            h.addWidget(go)
            r.mousePressEvent = lambda _e, to=target, n=name: self._tap(to, n)
            self._add(r)

    def _render_func_menu(self, data):
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, item in enumerate(data):
            r = QFrame()
            r.setObjectName("funcRow")
            r.setCursor(Qt.PointingHandCursor)
            h = QHBoxLayout(r)
            h.setContentsMargins(18, 16, 18, 16)
            h.setSpacing(16)
            # 设计稿 .func-menu .seq：40px 渐变序号块
            seq = QLabel(f"{i + 1:02d}")
            seq.setObjectName("funcSeq")
            seq.setFixedSize(40, 40)
            seq.setAlignment(Qt.AlignCenter)
            h.addWidget(seq)
            v = QVBoxLayout()
            v.setSpacing(3)
            name = QLabel(item["n"])
            name.setObjectName("funcName")
            v.addWidget(name)
            desc = QLabel(item["d"])
            desc.setObjectName("funcDesc")
            v.addWidget(desc)
            h.addLayout(v, 1)
            go = QPushButton("›")
            go.setObjectName("listGo")
            go.setFixedSize(26, 26)
            go.setCursor(Qt.PointingHandCursor)
            go.clicked.connect(lambda _=False, to=item["to"], n=item["n"]: self._tap(to, n))
            h.addWidget(go)
            r.mousePressEvent = lambda _e, to=item["to"], n=item["n"]: self._tap(to, n)
            grid.addWidget(r, i // 2, i % 2)
        for c in (0, 1):
            grid.setColumnStretch(c, 1)
        self._add_layout(grid)

    def _render_info_table(self, data):
        """对齐设计稿 .info-table：表头（项目/值）+ k 固定 200px 行。"""
        box = QFrame()
        box.setObjectName("ecTable")
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QFrame()
        head.setObjectName("ecHead")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(18, 12, 18, 12)
        hh.setSpacing(10)
        hk = QLabel("项目")
        hk.setObjectName("ecHeadL")
        hk.setFixedWidth(200)
        hh.addWidget(hk)
        hv = QLabel("值")
        hv.setObjectName("ecHeadL")
        hh.addWidget(hv, 1)
        v.addWidget(head)
        for k, val in data:
            r = QFrame()
            r.setObjectName("ecRow")
            h = QHBoxLayout(r)
            h.setContentsMargins(18, 12, 18, 12)
            h.setSpacing(10)
            kk = QLabel(k)
            kk.setObjectName("ecKey")
            kk.setFixedWidth(200)
            h.addWidget(kk)
            vv = QLabel(val)
            vv.setObjectName("ecVal")
            vv.setWordWrap(True)
            h.addWidget(vv, 1)
            v.addWidget(r)
        self._add(box)

    def _render_ec_table(self, data):
        """对齐设计稿 .ec-table：表头行 + 三列数据行（列宽按 _EC_CFG）。"""
        headers, stretches = self._EC_CFG.get(self._KIND, (("", "", ""), (1, 1, 1)))
        box = QFrame()
        box.setObjectName("ecTable")
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._ec_head(headers, stretches))
        for row in data:
            v.addWidget(self._ec_row_data(row))
        self._add(box)

    def _ec_head(self, headers, stretches) -> QFrame:
        head = QFrame()
        head.setObjectName("ecHead")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(18, 12, 18, 12)
        hh.setSpacing(10)
        for c, s in zip(headers, stretches):
            lbl = QLabel(c)
            lbl.setObjectName("ecHeadL")
            hh.addWidget(lbl, s)
        return head

    def _render_match_grid(self, data):
        """对齐设计稿 .match-grid：双列 grid，每组带头部序号徽章。"""
        grid = QGridLayout()
        grid.setSpacing(16)
        for g, group in enumerate(data):
            card = QFrame()
            _prop(card, "card", "matchGroup")
            v = QVBoxLayout(card)
            v.setContentsMargins(18, 16, 18, 16)
            v.setSpacing(8)
            th = QHBoxLayout()
            th.setSpacing(8)
            seq = QLabel(f"{g + 1:02d}")
            seq.setObjectName("matchSeq")
            seq.setFixedSize(24, 24)
            seq.setAlignment(Qt.AlignCenter)
            th.addWidget(seq)
            t = QLabel(group["n"])
            t.setObjectName("matchTitle")
            th.addWidget(t)
            th.addStretch(1)
            v.addLayout(th)
            v.addWidget(self._divider())
            for item in group["items"]:
                row = QHBoxLayout()
                k = QLabel(item["k"])
                k.setObjectName("ecKey")
                row.addWidget(k)
                row.addStretch(1)
                row.addWidget(self._match_control(item), 0, Qt.AlignRight)
                v.addLayout(row)
            grid.addWidget(card, g // 2, g % 2)
        for c in (0, 1):
            grid.setColumnStretch(c, 1)
        self._add_layout(grid)

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("matchLine")
        line.setFixedHeight(1)
        return line

    def _match_control(self, item):
        """对齐设计稿：select → 下拉框 / radio → 单选钮 / input → 文本框。"""
        typ = item.get("t", "select")
        if typ == "select":
            cb = QComboBox()
            cb.setObjectName("matchCombo")
            cb.addItems(item.get("opts", []))
            idx = cb.findText(str(item.get("v", "")))
            if idx >= 0:
                cb.setCurrentIndex(idx)
            cb.currentIndexChanged.connect(
                lambda _i, it=item: self._toast(f"{it['k']}：已选择（演示，未写入 ECU）"))
            return cb
        if typ == "radio":
            wrap = QFrame()
            wh = QHBoxLayout(wrap)
            wh.setContentsMargins(0, 0, 0, 0)
            wh.setSpacing(8)
            radios = []
            for opt in item.get("opts", []):
                rb = QRadioButton(str(opt))
                rb.setObjectName("matchRadio")
                rb.setCursor(Qt.PointingHandCursor)
                rb.setChecked(opt == item.get("v"))
                wh.addWidget(rb)
                radios.append((rb, opt))
            for rb, opt in radios:
                rb.toggled.connect(
                    lambda on, o=opt, it=item: on and self._toast(f"{it['k']}：{o}（演示，未写入 ECU）"))
            return wrap
        le = QLineEdit()
        le.setObjectName("matchInput")
        le.setPlaceholderText("--")
        le.setText(str(item.get("v", "")))
        le.returnPressed.connect(
            lambda it=item: self._toast(f"{it['k']}：已写入（演示，未写入 ECU）"))
        return le

    def _render_upd_list(self, data):
        for item in data:
            card = QFrame()
            _prop(card, "card", "updRow")
            v = QVBoxLayout(card)
            v.setContentsMargins(16, 14, 16, 14)
            v.setSpacing(8)
            head = QHBoxLayout()
            head.addWidget(SvgGlyph(SMALL.get(item["ic"], ""), size=22, stroke="acc", viewbox=24))
            name = QLabel(item["n"])
            name.setObjectName("updName")
            head.addWidget(name)
            head.addStretch(1)
            btn = QPushButton(item["btn"])
            btn.setObjectName("setVal")
            btn.setCursor(Qt.PointingHandCursor)
            if item.get("btnCls") == "disabled":
                btn.setEnabled(False)
            btn.clicked.connect(lambda _=False: self._toast("软件更新演示功能"))
            head.addWidget(btn)
            v.addLayout(head)
            for row in item["rows"]:
                rr = QHBoxLayout()
                k = QLabel(row["k"])
                k.setObjectName("updK")
                rr.addWidget(k)
                rr.addStretch(1)
                vv = QLabel(row["v"])
                vv.setObjectName("updV")
                if row.get("new"):
                    _prop(vv, "new", "on")
                if row.get("link"):
                    _prop(vv, "link", "on")
                    vv.setCursor(Qt.PointingHandCursor)
                    vv.mousePressEvent = lambda _e, s=row["v"]: self._toast(f"跳转演示：{s}")
                rr.addWidget(vv)
                v.addLayout(rr)
            self._add(card)

    # ── 行构造 ─────────────────────────────────

    def _ec_row(self, k, v, tag) -> QFrame:
        r = QFrame()
        r.setObjectName("ecRow")
        h = QHBoxLayout(r)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(10)
        kk = QLabel(k)
        kk.setObjectName("ecKey")
        h.addWidget(kk)
        h.addStretch(1)
        vv = QLabel(v)
        vv.setObjectName("ecVal")
        vv.setWordWrap(True)
        h.addWidget(vv, 1)
        if tag:
            tg = QLabel(tag)
            tg.setObjectName("ecTag")
            _prop(tg, "st", "cur" if tag == "当前故障" else ("ok" if tag == "正常" else "warn"))
            h.addWidget(tg)
        return r

    def _ec_row_data(self, row):
        if isinstance(row, list):      # EBS_DTC / EBS_TEST
            if len(row) >= 3 and row[0].startswith(("P", "B", "C", "U")):
                r = self._ec_row(row[0], row[1], row[2])
                r.mousePressEvent = lambda _e: self._dtc_modal(row[0], row[1])
                return r
            # EBS_TEST: [name, state, cls, act]
            name, state, cls_, act_ = row
            r = QFrame()
            r.setObjectName("ecRow")
            h = QHBoxLayout(r)
            h.setContentsMargins(14, 10, 14, 10)
            h.setSpacing(10)
            kk = QLabel(name)
            kk.setObjectName("ecKey")
            h.addWidget(kk)
            h.addStretch(1)
            tg = QLabel(state)
            tg.setObjectName("ecTag")
            _prop(tg, "st", cls_)
            h.addWidget(tg)
            ex = QPushButton("▶ 执行")
            ex.setProperty("role", "mini")
            ex.setCursor(Qt.PointingHandCursor)
            if act_ == "lock":
                # 设计稿：受限项目按钮置灰不可点击（opacity .5）
                ex.setEnabled(False)
            ex.clicked.connect(lambda _=False, n=name: self._toast(f"已发起测试：{n}（演示）"))
            h.addWidget(ex)
            return r
        # EBS_DF: dict {n, u, k}
        r = self._ec_row(row["n"], "—", "")
        return r

    # ── 点击处理 ───────────────────────────────

    def _tap(self, target, name):
        if target:
            self._go(target)
        else:
            self._toast(f"「{name}」演示功能")

    def _dtc_modal(self, code, desc):
        self._modal("故障码详情", f"{code}\n{desc}\n\n该故障码功能为演示数据，真实诊断请使用 DTS 设备。")

    def _go_back(self):
        self._go(self._BACK)


class SpecialPage(SkeletonPage):
    PAGE_ID = "special"
    _KIND = "grid5"
    _DATA = SPECIAL_ITEMS


class AdvancedPage(SkeletonPage):
    PAGE_ID = "advanced"
    _KIND = "grid4"
    _DATA = ADVANCED_ITEMS


class EbsEcuPage(SkeletonPage):
    PAGE_ID = "ebs"
    _KIND = "list"
    _DATA = EBS_ECU


class EbsFuncPage(SkeletonPage):
    PAGE_ID = "ebs-func"
    _KIND = "func-menu"
    _DATA = EBS_FUNCS


class EbsInfoPage(SkeletonPage):
    PAGE_ID = "ebs-info"
    _KIND = "info-table"
    _DATA = EBS_INFO


class EbsDtcPage(SkeletonPage):
    PAGE_ID = "ebs-dtc"
    _KIND = "ec-table"
    _DATA = EBS_DTC


class EbsDataflowPage(SkeletonPage):
    PAGE_ID = "ebs-dataflow"
    _KIND = "ec-table"
    _DATA = EBS_DF

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick = 0
        self._val_labels = None          # {k: ecVal QLabel}，首次进入时缓存
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        # 不再在 __init__ 常驻启动：仅当前页可见时运行（on_enter 启动 / on_leave 停止）

    def on_enter(self):
        super().on_enter()
        if self._val_labels is None:
            self._cache_labels()
        self._timer.start(200)

    def on_leave(self):
        super().on_leave()
        self._timer.stop()

    def _cache_labels(self):
        """一次性把 ecRow → ecVal QLabel 按 EBS_DF 顺序映射缓存，消除每 tick 全树扫描。"""
        self._val_labels = {}
        rows = [w for w in self.findChildren(QFrame) if w.objectName() == "ecRow"]
        for i, r in enumerate(rows):
            if i >= len(EBS_DF):
                break
            k = EBS_DF[i]["k"]
            for lbl in r.findChildren(QLabel):
                if lbl.objectName() == "ecVal":
                    self._val_labels[k] = lbl
                    break

    def _refresh(self):
        self._tick += 1
        for i, d in enumerate(EBS_DF):
            k = d["k"]
            amp = _DF_AMP.get(k)
            if amp is None:
                continue                        # 静态行不动
            lbl = (self._val_labels or {}).get(k)
            if lbl is None:
                continue
            val = _DF_BASE[k] + amp * math.sin(self._tick * 0.6 + i)
            fmt = "%.0f" if amp >= 1 else "%.1f"
            lbl.setText(f"{fmt % val} {d['u']}".strip())


class EbsTestPage(SkeletonPage):
    PAGE_ID = "ebs-test"
    _KIND = "ec-table"
    _DATA = EBS_TEST


class EbsMatchPage(SkeletonPage):
    PAGE_ID = "ebs-match"
    _KIND = "match-grid"
    _DATA = MATCH_GROUPS


class CanPage(SkeletonPage):
    PAGE_ID = "can"
    _KIND = "list"
    _DATA = CAN_LIST


class UpdatePage(SkeletonPage):
    PAGE_ID = "update"
    _KIND = "upd-list"
    _DATA = UPDATES
