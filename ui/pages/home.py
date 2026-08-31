"""主页：设备选择 + 常见故障现象 + AI 输入条 + 快捷服务。"""

import json

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton, QFrame,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ui.lcsdata import DEFAULT_DEVICES, DEV_ICONS, SMALL, SYMPTOMS
from ui.pages.base import LcsPage
from ui.widgets import (
    ClipIcon, DevCard, SendButton, SparkIcon, SvgGlyph, _prop,
)

ORG, APP = "AutoDrive", "AutoDrive"


class _AddTile(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        _prop(self, "card", "dev-add")
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignCenter)
        v.setSpacing(8)
        plus = QLabel("+")
        plus.setObjectName("devAddPlus")
        plus.setAlignment(Qt.AlignCenter)
        v.addWidget(plus)
        lbl = QLabel("添加您的设备")
        lbl.setObjectName("devAddLabel")
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _SympItem(QFrame):
    """故障现象多选项（对齐设计稿 .symp-item）：16px 勾选框 + 文本，选中态由 sel 属性驱动。"""

    clicked = Signal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        _prop(self, "symp", "item")
        _prop(self, "sel", "off")
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)   # 内边距走 theme.qss [symp="item"] padding
        h.setSpacing(7)
        self._chk = QLabel("✓")
        self._chk.setObjectName("sympChk")  # 16x16 由 theme.qss min/max 约束
        self._chk.setAlignment(Qt.AlignCenter)
        h.addWidget(self._chk)
        lbl = QLabel(text)
        lbl.setObjectName("sympText")
        h.addWidget(lbl)

    def set_selected(self, on: bool):
        _prop(self, "sel", "on" if on else "off")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._text)
        super().mousePressEvent(event)


class _QuickTile(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str, icon: str, label: str, sub: str = "", parent=None):
        super().__init__(parent)
        self._key = key
        _prop(self, "card", "quick")
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)   # 内边距走 theme.qss [card="quick"] padding
        v.setSpacing(6)
        v.setAlignment(Qt.AlignCenter)
        v.addWidget(SvgGlyph(DEV_ICONS.get(icon, ""), size=22, stroke="acc"), 0, Qt.AlignCenter)
        lbl = QLabel(label)
        lbl.setObjectName("quickName")
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setObjectName("quickSub")
            sub_lbl.setAlignment(Qt.AlignCenter)
            v.addWidget(sub_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


class HomePage(LcsPage):
    PAGE_ID = "home"

    start_ai_requested = Signal(str, str, list)   # (device_id, question, symptoms)
    devices_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qs = QSettings(ORG, APP)
        self._devices = self._load_devices()
        self._selected = None
        self._sel_items = set()
        self._cur_cat = SYMPTOMS[0]["cat"] if SYMPTOMS else ""
        self._build_ui()

    # ── 设备持久化 ─────────────────────────────

    def _load_devices(self) -> list:
        deleted = set(json.loads(self._qs.value("ui/deleted_devices", "[]")))
        devs = [d for d in DEFAULT_DEVICES if d["id"] not in deleted]
        try:
            extra = json.loads(self._qs.value("ui/devices", "[]"))
            devs += [d for d in extra if d.get("id")]
        except Exception:
            pass
        return devs

    def _save_devices(self):
        defaults = {d["id"] for d in DEFAULT_DEVICES}
        extra = [d for d in self._devices if d["id"] not in defaults]
        deleted = [d["id"] for d in DEFAULT_DEVICES if d["id"] not in {x["id"] for x in self._devices}]
        self._qs.setValue("ui/devices", json.dumps(extra, ensure_ascii=False))
        self._qs.setValue("ui/deleted_devices", json.dumps(deleted))

    # ── UI 构建 ───────────────────────────────

    def _centered_host(self, name: str, inner) -> QHBoxLayout:
        """返回水平居中、限宽容器 row。宽度上限写于 theme.qss（#name），
        需配合 Expanding 水平策略生效；Python 侧不写死像素宽度。"""
        host = QFrame()
        host.setObjectName(name)
        host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        hv = QVBoxLayout(host)
        hv.setContentsMargins(0, 0, 0, 0)
        if isinstance(inner, QLayout):
            hv.addLayout(inner)
        else:
            hv.addWidget(inner)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        # host 给 stretch 因子：两侧 spacer 弹性均分，host 撑满到 QSS max-width 上限后居中
        row.addStretch(1)
        row.addWidget(host, 1)
        row.addStretch(1)
        return row

    def _section_title(self, text: str, small: bool = False) -> QVBoxLayout:
        """设计稿 section-title：居中标题 + 渐变装饰线（尺寸在 theme.qss #secLine）。"""
        v = QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        t = QLabel(text)
        t.setObjectName("homeTitle")
        if small:
            _prop(t, "sz", "sm")
        t.setAlignment(Qt.AlignCenter)
        line = QFrame()
        line.setObjectName("secLine")
        v.addWidget(t)
        v.addWidget(line, 0, Qt.AlignHCenter)
        return v

    def _build_ui(self):
        self._add_layout(self._section_title("选择您使用的设备"))

        self._dev_grid = QGridLayout()
        self._dev_grid.setSpacing(12)
        self._rebuild_dev_cards()
        # 设备网格限宽 754px 居中（设计稿 .dev-grid max-width:754px; margin:0 auto）
        self._add_layout(self._centered_host("devGridHost", self._dev_grid))

        # ── 常见故障现象（设计稿 .symp-wrap：max-width 920px 居中） ──
        self._add_layout(self._section_title("常见故障现象"))
        self._cat_row = QHBoxLayout()
        self._cat_row.setSpacing(8)
        self._item_flow = QHBoxLayout()
        self._item_flow.setSpacing(10)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(14)
        wrap.addLayout(self._cat_row)
        wrap.addLayout(self._item_flow)
        self._add_layout(self._centered_host("sympHost", wrap))
        self._rebuild_cats()

        # ── AI 输入条（设计稿 .ai-bar：max-width 760 居中，padding/圆角在 theme.qss） ──
        bar = QFrame()
        _prop(bar, "card", "ai-bar")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(10)
        bh.addWidget(SparkIcon(size=18))
        self._ai_text = QLineEdit()
        self._ai_text.setObjectName("aiText")
        self._ai_text.setPlaceholderText("描述您的车辆问题...")
        bh.addWidget(self._ai_text, 1)
        attach = QPushButton("📎")
        attach.setObjectName("attachBtn")
        attach.setCursor(Qt.PointingHandCursor)
        attach.setToolTip("上传图片（演示）")
        attach.clicked.connect(lambda: self._toast("图片上传功能演示中"))
        bh.addWidget(attach)
        voice = QPushButton("🎤")
        voice.setObjectName("voiceBtn")
        voice.setCursor(Qt.PointingHandCursor)
        voice.setToolTip("语音输入（演示）")
        voice.clicked.connect(lambda: self._toast("语音输入功能演示中"))
        bh.addWidget(voice)
        self._send_btn = SendButton(size=36)
        self._send_btn.setObjectName("SendBtn")
        self._send_btn.setToolTip("已收到描述，请点击底部「开始AI智能诊断」")
        self._send_btn.clicked.connect(lambda: self._toast("已收到，请点击底部「开始AI智能诊断」"))
        bh.addWidget(self._send_btn)
        self._add_layout(self._centered_host("aiBarHost", bar))

        # ── 快捷服务 4 宫格（设计稿 .quick-grid：max-width 645 居中） ──
        self._add_layout(self._section_title("快捷服务", small=True))
        grid = QGridLayout()
        grid.setSpacing(12)
        quicks = [
            ("report", "check", "诊断报告", "查看历史诊断"),
            ("remote", "bluetooth", "远程协助", "专家远程支持"),
            ("account", "home", "用户中心", "账户 / 授权 / 统计"),
            ("settings", "theme", "系统设置", "主题 / 语言 / 关于"),
        ]
        for i, (pid, icon, label, sub) in enumerate(quicks):
            t = _QuickTile(pid, icon, label, sub)
            t.clicked.connect(self._go)
            grid.addWidget(t, i // 4, i % 4)
        self._add_layout(self._centered_host("quickHost", grid))

        foot = QLabel("Runch AI 提供技术支持 · 内容仅供参考，如有进一步的技术问题，可以请求专家远程技术支持")
        foot.setObjectName("SecHint")
        foot.setAlignment(Qt.AlignCenter)
        self._add(foot)

    def _rebuild_dev_cards(self):
        while self._dev_grid.count():
            item = self._dev_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._dev_cards = {}
        for i, dev in enumerate(self._devices):
            card = DevCard(dev)
            card.clicked.connect(self.select_device)
            card.delete_requested.connect(self._delete_device)
            card.set_selected(dev["id"] == self._selected)
            self._dev_grid.addWidget(card, i // 4, i % 4)
            self._dev_cards[dev["id"]] = card
        add = _AddTile()
        add.clicked.connect(self._add_device_modal)
        self._dev_grid.addWidget(add, len(self._devices) // 4, len(self._devices) % 4)
        # 固定 4 列（对齐设计稿 .dev-grid grid-template-columns:repeat(4,1fr)）
        for c in range(4):
            self._dev_grid.setColumnStretch(c, 1)

    def _rebuild_cats(self):
        while self._cat_row.count():
            item = self._cat_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._symp_cat_btns = []
        for cat in SYMPTOMS:
            b = QPushButton(cat["cat"])
            b.setProperty("role", "symp-cat")
            b.setCursor(Qt.PointingHandCursor)
            _prop(b, "sel", "on" if cat["cat"] == self._cur_cat else "off")
            b.clicked.connect(lambda _=False, c=cat["cat"]: self._switch_cat(c))
            self._cat_row.addWidget(b)
            self._symp_cat_btns.append(b)
        self._rebuild_items()

    def _rebuild_items(self):
        while self._item_flow.count():
            item = self._item_flow.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._symp_item_btns = []
        for cat in SYMPTOMS:
            if cat["cat"] != self._cur_cat:
                continue
            for item in cat["items"]:
                b = _SympItem(item)
                b.clicked.connect(self._toggle_item)
                b.set_selected(item in self._sel_items)
                self._item_flow.addWidget(b)
                self._symp_item_btns.append(b)
        self._item_flow.addStretch(1)

    # ── 交互 ──────────────────────────────────

    def _switch_cat(self, cat: str):
        self._cur_cat = cat
        for b, c in zip(self._symp_cat_btns, SYMPTOMS):
            _prop(b, "sel", "on" if c["cat"] == cat else "off")
        self._rebuild_items()

    def _toggle_item(self, item: str):
        if item in self._sel_items:
            self._sel_items.discard(item)
        else:
            self._sel_items.add(item)
        for b in self._symp_item_btns:
            if isinstance(b, _SympItem):
                b.set_selected(b._text in self._sel_items)

    def select_device(self, dev_id: str):
        self._selected = dev_id
        for did, card in self._dev_cards.items():
            card.set_selected(did == dev_id)
        self.devices_changed.emit()

    def _add_device_modal(self):
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        name_edit = QLineEdit()
        name_edit.setObjectName("aiText")
        name_edit.setPlaceholderText("设备名称，如：您的设备4：威易")
        v.addWidget(name_edit)
        icon_row = QHBoxLayout()
        icon_row.setSpacing(10)
        icon_btns = []
        chosen = [None]

        def _pick(icon):
            chosen[0] = icon
            for (ic, _b) in icon_btns:
                _prop(_b, "sel", "on" if ic == icon else "off")

        for icon in ["sedan", "suv", "truck", "ev", "wrench", "chip"]:
            b = QPushButton()
            b.setObjectName("iconPick")   # 46x46 由 theme.qss min/max 约束
            b.setCursor(Qt.PointingHandCursor)
            _prop(b, "sel", "off")
            gly = SvgGlyph(DEV_ICONS[icon], size=28, stroke="acc")
            lay = QVBoxLayout(b)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(gly, 0, Qt.AlignCenter)
            b.clicked.connect(lambda _=False, ic=icon: _pick(ic))
            icon_row.addWidget(b)
            icon_btns.append((icon, b))
        v.addLayout(icon_row)
        v.addWidget(QLabel("点击图标选择设备样式"))
        self._modal("添加您的设备", "", "保存", "取消",
                    lambda: self._add_device(name_edit.text().strip(), chosen[0]),
                    content=content)

    def _add_device(self, name: str, icon: str):
        if not name:
            self._toast("请输入设备名称", "crit")
            return
        nid = f"c{len(self._devices) + 1}"
        self._devices.append({
            "id": nid, "n": name, "icon": icon or "sedan", "cls": "",
            "system": "自定义设备", "obd": "自定义诊断设备",
        })
        self._save_devices()
        self._rebuild_dev_cards()
        self.devices_changed.emit()
        self._toast("设备已添加")

    def _delete_device(self, dev_id: str):
        dev = self._devices
        self._devices = [d for d in dev if d["id"] != dev_id]
        if self._selected == dev_id:
            self._selected = None
        self._save_devices()
        self._rebuild_dev_cards()
        self.devices_changed.emit()
        self._toast("设备已删除")

    # ── 接口（wizard / 测试） ─────────────────

    def selected_device_id(self):
        return self._selected

    def selected_device(self):
        for d in self._devices:
            if d["id"] == self._selected:
                return d
        return None

    def selected_symptoms(self):
        return sorted(self._sel_items)

    def question_text(self):
        return self._ai_text.text().strip()

    def has_input(self):
        return bool(self.question_text() or self._sel_items)

    def clear(self):
        self._ai_text.clear()
        self._sel_items.clear()
        self._rebuild_items()
