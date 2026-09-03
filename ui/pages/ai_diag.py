"""AI 智能诊断页：远驰AI 诊断过程 + 当前车辆信息 + AI 诊断结果 + 排查步骤。"""

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.pages.base import LcsPage
from ui.report import ReportLoader
from ui.widgets import (
    GlassCard, GradBar, PhaseBar, StatusTag, _prop,
)

__all__ = ["AiDiagPage"]


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()


class AiDiagPage(LcsPage):
    PAGE_ID = "ai-diagn"

    restart_requested = Signal()
    export_requested = Signal(object)   # result dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._body.setContentsMargins(26, 20, 26, 20)
        self._body.setSpacing(18)
        self._device_name = ""
        self._question = ""
        self._result = None
        self._out_dir = None
        self._steps = []
        self._sel_step = 0
        self._build_ui()
        self._set_waiting()

    # ── UI ─────────────────────────────────────

    def _build_ui(self):
        # 面包屑
        crumb = QHBoxLayout()
        crumb.setContentsMargins(0, 0, 0, 0)
        crumb.setSpacing(8)
        back = QPushButton("‹ 返回")
        back.setObjectName("CrumbBack")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._go("home"))
        crumb.addWidget(back)
        self._crumb_text = QLabel("AI 智能诊断")
        self._crumb_text.setObjectName("CrumbText")
        crumb.addWidget(self._crumb_text)
        crumb.addStretch(1)
        self._vin_tag = QLabel("")
        self._vin_tag.setObjectName("VinTag")
        self._vin_tag.hide()
        crumb.addWidget(self._vin_tag)
        self._add_layout(crumb)

        # 四节点步进器
        self._steps_bar = PhaseBar()
        self._add(self._steps_bar)

        # ── 远驰AI 诊断过程 ──
        dyn = GlassCard()
        head = QHBoxLayout()
        head.setSpacing(10)
        avatar = QLabel("AI")
        avatar.setObjectName("aiAvatar")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignCenter)
        head.addWidget(avatar)
        t = QLabel("远驰AI 诊断过程")
        t.setObjectName("resultTitle")
        head.addWidget(t)
        head.addStretch(1)
        self._dyn_status = QLabel("等待开始")
        self._dyn_status.setObjectName("dynStatus")
        _prop(self._dyn_status, "state", "running")
        head.addWidget(self._dyn_status)
        dyn.layout.addLayout(head)
        self._dyn_list = QVBoxLayout()
        self._dyn_list.setSpacing(6)
        dyn.layout.addLayout(self._dyn_list)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("SecHint")
        dyn.layout.addWidget(self._status_lbl)
        self._dyn_card = dyn
        self._add(dyn)

        # ── 当前车辆信息 ──
        veh = GlassCard()
        veh_head = QHBoxLayout()
        t = QLabel("当前车辆信息")
        t.setObjectName("resultTitle")
        veh_head.addWidget(t)
        veh_head.addStretch(1)
        veh.layout.addLayout(veh_head)
        self._veh_vals = {}
        grid = QVBoxLayout()
        grid.setSpacing(6)
        for key, label in (("vin", "VIN"), ("model", "车型"), ("mileage", "里程"), ("ecu", "ECU")):
            row = QHBoxLayout()
            k = QLabel(label)
            k.setObjectName("vehKey")
            k.setFixedWidth(44)
            row.addWidget(k)
            v = QLabel("—")
            v.setObjectName("vehVal")
            v.setWordWrap(True)
            row.addWidget(v, 1)
            grid.addLayout(row)
            self._veh_vals[key] = v
        veh.layout.addLayout(grid)
        self._veh_dtc_list = QVBoxLayout()
        self._veh_dtc_list.setSpacing(6)
        veh.layout.addLayout(self._veh_dtc_list)
        self._veh_card = veh
        self._add(veh)

        # ── AI 诊断结果 ──
        self._result_card = GlassCard()
        r_head = QHBoxLayout()
        t = QLabel("AI 诊断结果")
        t.setObjectName("resultTitle")
        r_head.addWidget(t)
        r_head.addStretch(1)
        self._result_tag = StatusTag("分析完成", "ok")
        self._result_tag.hide()
        r_head.addWidget(self._result_tag)
        self._result_card.layout.addLayout(r_head)
        self._result_meta = QLabel("")
        self._result_meta.setObjectName("resultMeta")
        self._result_card.layout.addWidget(self._result_meta)
        self._causes_lay = QVBoxLayout()
        self._causes_lay.setSpacing(10)
        self._result_card.layout.addLayout(self._causes_lay)
        # 排查步骤
        self._steps_title = QLabel("建议排查步骤")
        self._steps_title.setObjectName("SecTitle")
        self._result_card.layout.addWidget(self._steps_title)
        split = QHBoxLayout()
        split.setSpacing(12)
        self._steps_left = QVBoxLayout()
        self._steps_left.setSpacing(4)
        left_wrap = QWidget()
        left_wrap.setLayout(self._steps_left)
        left_wrap.setFixedWidth(260)
        split.addWidget(left_wrap)
        self._step_detail = GlassCard(padding=14)
        self._step_title = QLabel("")
        self._step_title.setObjectName("stepTitle")
        self._step_title.setWordWrap(True)
        self._step_detail.layout.addWidget(self._step_title)
        self._step_body = QVBoxLayout()
        self._step_body.setSpacing(8)
        self._step_detail.layout.addLayout(self._step_body)
        split.addWidget(self._step_detail, 1)
        self._result_card.layout.addLayout(split)
        self._step_pager = QLabel("")
        self._step_pager.setObjectName("SecHint")
        self._step_pager.setAlignment(Qt.AlignCenter)
        self._result_card.layout.addWidget(self._step_pager)
        self._add(self._result_card)

        # 操作按钮
        act = QHBoxLayout()
        act.setSpacing(12)
        act.addStretch(1)
        self._restart_btn = QPushButton("重新诊断")
        self._restart_btn.setProperty("role", "ghost")
        self._restart_btn.setCursor(Qt.PointingHandCursor)
        self._restart_btn.clicked.connect(self.restart_requested.emit)
        act.addWidget(self._restart_btn)
        self._export_btn = QPushButton("导出诊断报告")
        self._export_btn.setProperty("role", "primary")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.clicked.connect(lambda: self.export_requested.emit(self._result))
        act.addWidget(self._export_btn)
        self._add_layout(act)

        # 底部免责声明（对齐设计稿 ai 页底部）
        note = QLabel("Runch AI 提供的建议仅供参考 · 重大故障请咨询专业维修站处理")
        note.setObjectName("SecHint")
        note.setAlignment(Qt.AlignCenter)
        self._add(note)

    # ── 等待 / 运行状态 ────────────────────────

    def _set_waiting(self):
        """整页回到空态（重新执行时调用）：清空上一次的动态信息 / 车辆信息 /
        故障码 / 诊断结果，等待新流程的内容渲染，而不是旧内容残留。"""
        self._status_lbl.setText("等待运行数据")
        self._dyn_status.setText("等待开始")
        _prop(self._dyn_status, "state", "running")
        self._result_tag.hide()
        _clear(self._causes_lay)
        _clear(self._steps_left)
        _clear(self._step_body)
        self._step_pager.setText("")
        self._steps = []
        self._steps_title.hide()
        _clear(self._dyn_list)
        for v in self._veh_vals.values():
            v.setText("—")
        _clear(self._veh_dtc_list)
        self._vin_tag.hide()
        self._result_meta.setText("")
        self._result = None
        self._out_dir = None

    # ── 旧 AiPage 方法名兼容（wizard / 测试） ────

    def set_phase(self, phase):
        self._steps_bar.set_phase(phase)

    def set_stage(self, no, state, text):
        self.set_dyn_status(text)

    def set_running(self, running):
        for b in (self._restart_btn, self._export_btn):
            b.setEnabled(not running)
        if running:
            self._status_lbl.setText("诊断中…")

    def set_status(self, text):
        self._status_lbl.setText(text)

    def set_badge(self, state):
        if state == "done":
            self._result_tag.setText("分析完成")
            self._result_tag.set_kind("ok")
            self._result_tag.show()
        elif state == "running":
            self._result_tag.setText("分析中")
            self._result_tag.set_kind("acc")
            self._result_tag.show()
        else:
            self._result_tag.hide()

    def reset(self):
        self._set_waiting()

    def show_error(self, msg):
        self.append_dyn(msg, cls="error")
        self.set_status(f"失败：{msg}")
        _prop(self._dyn_status, "state", "error")

    def get_input(self):
        return self._question, ""

    def set_summary(self, device, symptom=""):
        self._question = symptom or ""
        self.set_meta(device)

    def set_vehicle(self, name):
        self.set_meta(name)

    def focus_input(self):
        pass

    # ── 动态信息 ───────────────────────────────

    def append_dyn(self, msg, cls=""):
        row = QFrame()
        row.setObjectName("dynMsg")
        _prop(row, "cls", cls)
        h = QHBoxLayout(row)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(8)
        dot = QLabel("")
        dot.setObjectName("dynDot")
        dot.setFixedSize(6, 6)
        _prop(dot, "cls", cls)
        h.addWidget(dot)
        text = QLabel(msg)
        text.setObjectName("dynText")
        text.setWordWrap(True)
        h.addWidget(text, 1)
        ts = QLabel(QTime.currentTime().toString("HH:mm:ss"))
        ts.setObjectName("dynTs")
        h.addWidget(ts)
        self._dyn_list.addWidget(row)

    def set_dyn_status(self, text, state=None):
        if state is None:
            if "完成" in text or "成功" in text:
                state = "done"
            elif "思考" in text:
                state = "thinking"
            elif "失败" in text or "错误" in text:
                state = "error"
            else:
                state = "running"
        self._dyn_status.setText(text)
        _prop(self._dyn_status, "state", state)

    # ── 车辆 / 故障码 ──────────────────────────

    def set_meta(self, dev_name):
        self._device_name = dev_name or ""
        self._crumb_text.setText(f"{self._device_name} 诊断" if self._device_name else "AI 智能诊断")

    def set_vin(self, info: dict):
        for key, v in self._veh_vals.items():
            v.setText(info.get(key, "—"))
        vin = info.get("vin", "")
        if vin:
            self._vin_tag.setText(f"VIN · {vin}")
            self._vin_tag.show()
        else:
            self._vin_tag.hide()

    def set_faults(self, faults):
        _clear(self._veh_dtc_list)
        for f in faults or []:
            if isinstance(f, dict):
                code = f.get("code", "") or ""
                desc = f.get("desc", "") or ""
                st = f.get("status", "his") or "his"
            else:
                # FaultCode dataclass：severity=crit → 当前故障，否则历史故障
                code = getattr(f, "code", "") or ""
                desc = getattr(f, "desc", "") or ""
                sev = getattr(f, "severity", "warn") or "warn"
                st = "cur" if sev == "crit" else "his"
            row = QFrame()
            row.setObjectName("dtcRow")
            _prop(row, "st", st)
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 8, 12, 8)
            h.setSpacing(10)
            code_lbl = QLabel(code)
            code_lbl.setObjectName("dtcCode")
            h.addWidget(code_lbl)
            d = QLabel(desc)
            d.setObjectName("dtcDesc")
            d.setWordWrap(True)
            h.addWidget(d, 1)
            tag = QLabel("当前故障" if st == "cur" else "历史故障")
            tag.setObjectName("dtcTag")
            _prop(tag, "st", st)
            h.addWidget(tag)
            self._veh_dtc_list.addWidget(row)

    def set_report(self, report):
        """report 为 Report（真实或演示）；None 回到等待态。"""
        if report is None:
            self._set_waiting()
            return
        self._out_dir = report.out_dir
        info = self._parse_version(report.version)
        self.set_vin(info)
        self.set_faults(report.faults)

    def _parse_version(self, version: str) -> dict:
        info = {"vin": "", "model": "", "mileage": "", "ecu": ""}
        for line in (version or "").splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip().upper()
                v = v.strip()
                if k in ("VIN", "VIN码"):
                    info["vin"] = v
                elif k in ("车型", "MODEL"):
                    info["model"] = v
                elif k in ("里程", "MILEAGE"):
                    info["mileage"] = v
                elif k in ("ECU", "ECU软件号", "ECU软件"):
                    info["ecu"] = v
        return info

    # ── 采集计划 / 路试 / 报告 ──────────────────

    def show_plan(self, plan):
        streams = plan.get("streams", [])
        cond = plan.get("working_conditions", "")
        self.append_dyn(f"采集计划已生成：{len(streams)} 项数据流{(' · ' + cond) if cond else ''}", cls="done")
        self.set_dyn_status("采集计划已确认")

    def show_locatability(self, loc):
        ok_loc = bool(loc.get("is_locatable"))
        reason = loc.get("reason", "")
        text = "可原地定位 · 无需路试" if ok_loc else "需要路试"
        self.append_dyn(f"路试判断：{text}{(' · ' + reason) if reason else ''}", cls="done")
        self.set_dyn_status("路试判断完成")

    def show_report(self, data):
        self._result = data
        diag_list = data.get("diagnosisList", []) if isinstance(data, dict) else []
        self.render_causes(diag_list)
        if diag_list:
            meta = data.get("_meta", "")
            self._result_meta.setText(meta or f"共 {len(diag_list)} 条可能原因")
        self.set_badge("done")

    # ── 结果渲染 ───────────────────────────────

    def _pct_of(self, probability) -> float:
        if not probability:
            return 0.3
        s = str(probability).replace("%", "").strip()
        try:
            return max(0.05, min(1.0, float(s) / 100.0))
        except ValueError:
            pass
        low = str(probability)
        if "最大" in low or "最可能" in low:
            return 0.75
        if "次高" in low or "值得怀疑" in low:
            return 0.4
        if "较少" in low or "可能" in low:
            return 0.15
        return 0.3

    def _pl_of(self, pct: float) -> str:
        return "high" if pct >= 0.6 else ("mid" if pct >= 0.3 else "low")

    def render_causes(self, diag_list):
        _clear(self._causes_lay)
        for i, c in enumerate(diag_list or [], start=1):
            pct = self._pct_of(c.get("probability"))
            row = QFrame()
            row.setObjectName("causeRow")
            v = QVBoxLayout(row)
            v.setContentsMargins(14, 12, 14, 12)
            v.setSpacing(6)
            top = QHBoxLayout()
            top.setSpacing(10)
            rank = QLabel(f"{i:02d}")
            rank.setObjectName("causeRank")
            rank.setFixedSize(30, 26)
            rank.setAlignment(Qt.AlignCenter)
            top.addWidget(rank)
            mid = QVBoxLayout()
            mid.setSpacing(2)
            name = QLabel(c.get("faultPoint", f"原因 {i}"))
            name.setObjectName("causeName")
            mid.addWidget(name)
            desc = QLabel(c.get("simpleExplanation", ""))
            desc.setObjectName("causeDesc")
            desc.setWordWrap(True)
            mid.addWidget(desc)
            top.addLayout(mid, 1)
            prob = QLabel(str(c.get("probability", "")))
            prob.setObjectName("causeProb")
            _prop(prob, "pl", self._pl_of(pct))
            top.addWidget(prob)
            v.addLayout(top)
            bar = GradBar()
            bar.set_value(pct)
            v.addWidget(bar)
            self._causes_lay.addWidget(row)
        self._steps_title.show()

    # ── 排查步骤 ───────────────────────────────

    def _normalize_steps(self, steps):
        if isinstance(steps, dict):
            out = []
            for c in steps.get("diagnosisList", []):
                lines = []
                se = c.get("simpleExplanation")
                if se:
                    lines.append(("原因分析", se))
                gs = c.get("guideSteps") or []
                if gs:
                    lines.append(("排查处方", " / ".join(gs)))
                out.append({"title": c.get("faultPoint", "排查项"), "body_lines": lines})
            return out
        out = []
        for s in steps or []:
            lines = []
            if s.get("lineDef"):
                lines.append(("线路定义", s["lineDef"]))
            pins = s.get("pins")
            if pins:
                lines.append(("针脚定义", "；".join(f"{p['n']}：{p['d']}" for p in pins)))
            for k, lbl in (("step1", "第一步"), ("position", "位置说明"),
                           ("how", "测量方法"), ("see", "判断标准"),
                           ("aid", "辅助建议"), ("warn", "注意事项")):
                if s.get(k):
                    lines.append((lbl, s[k]))
            out.append({"title": s.get("title", ""), "body_lines": lines})
        return out

    def render_steps(self, diag_steps):
        self._steps = self._normalize_steps(diag_steps)
        self._sel_step = 0
        _clear(self._steps_left)
        for i, step in enumerate(self._steps):
            b = QPushButton(step.get("title", f"第 {i + 1} 步"))
            b.setObjectName("stepItem")
            b.setCursor(Qt.PointingHandCursor)
            _prop(b, "sel", "on" if i == 0 else "off")
            b.clicked.connect(lambda _=False, idx=i: self._select_step(idx))
            self._steps_left.addWidget(b)
        self._render_step_detail()

    def _select_step(self, idx):
        self._sel_step = idx
        for i in range(self._steps_left.count()):
            w = self._steps_left.itemAt(i).widget()
            if w is not None and isinstance(w, QPushButton):
                _prop(w, "sel", "on" if i == idx else "off")
        self._render_step_detail()

    def _render_step_detail(self):
        if not self._steps:
            self._step_pager.setText("")
            return
        step = self._steps[self._sel_step]
        self._step_title.setText(step.get("title", ""))
        _clear(self._step_body)
        for k, text in step.get("body_lines", []):
            row = QVBoxLayout()
            row.setSpacing(2)
            kk = QLabel(k)
            kk.setObjectName("stepK")
            row.addWidget(kk)
            vv = QLabel(text)
            vv.setObjectName("stepV")
            vv.setWordWrap(True)
            row.addWidget(vv)
            self._step_body.addLayout(row)
        n = len(self._steps)
        self._step_pager.setText(f"{self._sel_step + 1} / {n}")

    # ── 报告文本（测试 / 导出） ──────────────────

    def _report_texts(self):
        parts = []
        for lbl in self._result_card.findChildren(QLabel):
            t = lbl.text()
            if t:
                parts.append(t)
        return "\n".join(parts)

    def load_from(self, out_dir):
        report = ReportLoader().load(out_dir)
        self.set_report(report)
        plan = out_dir / "ai_collection_plan.json"
        if plan.exists():
            self.append_dyn(f"已恢复采集计划（{out_dir.name}）", cls="done")
