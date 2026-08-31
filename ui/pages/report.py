"""诊断报告页：报告列表（真实 ReportStore / 演示种子）+ 白纸详情。"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.lcsdata import DEMO_REPORTS
from ui.pages.base import LcsPage
from ui.report import (
    ReportLoader, ReportMeta, ReportStore, build_demo_ai_report, build_demo_report,
)
from ui.widgets import GlassCard, StatusTag, _prop

__all__ = ["ReportListPage"]

_CATS = ["时间", "设备", "概述", "操作"]


class ReportListPage(LcsPage):
    PAGE_ID = "report"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ReportStore()
        self._loader = ReportLoader()
        self._paper = None
        self._build_ui()

    def _build_ui(self):
        head = QHBoxLayout()
        t = QLabel("诊断报告")
        t.setObjectName("homeTitle")
        head.addWidget(t)
        head.addStretch(1)
        self._count_tag = StatusTag("", "acc")
        head.addWidget(self._count_tag)
        self._add_layout(head)

        # 白纸详情（点击列表行后出现）
        self._paper = GlassCard()
        self._paper_lay = QVBoxLayout()
        self._paper_lay.setSpacing(10)
        self._paper.layout.addLayout(self._paper_lay)
        self._paper.hide()
        self._add(self._paper)

        self._list = QVBoxLayout()
        self._list.setSpacing(8)
        self._add_layout(self._list)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        metas = self._store.list_reports()
        demo = not metas
        if demo:
            metas = [ReportMeta(time=r["time"], dev=r["dev"], summary=r["summary"])
                     for r in DEMO_REPORTS]
        self._count_tag.setText(f"{len(metas)} 份报告" + (" · 演示数据" if demo else ""))
        while self._list.count():
            item = self._list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not metas:
            hint = QLabel("暂无诊断报告，请先运行一次 AI 智能诊断")
            hint.setObjectName("SecHint")
            hint.setAlignment(Qt.AlignCenter)
            self._list.addWidget(hint)
            return
        # 表头
        head = QFrame()
        hh = QHBoxLayout(head)
        hh.setContentsMargins(14, 6, 14, 6)
        hh.setSpacing(12)
        for i, c in enumerate(_CATS):
            lbl = QLabel(c)
            lbl.setObjectName("SecTitle")
            if i == 2:
                hh.addWidget(lbl, 1)
            else:
                hh.addWidget(lbl)
        self._list.addWidget(head)
        for meta in metas:
            self._list.addWidget(self._row(meta, demo=demo))

    def _row(self, meta, demo=False) -> QFrame:
        row = QFrame()
        _prop(row, "card", "report-row")
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)
        time_lbl = QLabel(meta.time)
        time_lbl.setObjectName("repTime")
        time_lbl.setFixedWidth(120)
        h.addWidget(time_lbl)
        dev = QLabel(meta.dev)
        dev.setObjectName("repDev")
        h.addWidget(dev)
        s = QLabel(meta.summary or "（无摘要）")
        s.setObjectName("repSummary")
        s.setWordWrap(True)
        h.addWidget(s, 1)
        view = QPushButton("查看")
        view.setProperty("role", "mini")
        view.setCursor(Qt.PointingHandCursor)
        view.clicked.connect(lambda _=False, m=meta: self._open_paper(m, demo))
        h.addWidget(view)
        if not demo:
            dele = QPushButton("删除")
            dele.setProperty("role", "mini")
            dele.setCursor(Qt.PointingHandCursor)
            dele.clicked.connect(lambda _=False, m=meta: self._delete(m))
            h.addWidget(dele)
        return row

    def _delete(self, meta):
        if self._store.delete(meta):
            self._toast("报告已删除")
            self.refresh()

    def _open_paper(self, meta, demo=False):
        while self._paper_lay.count():
            item = self._paper_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if demo:
            report = build_demo_report()
            ai = build_demo_ai_report()
        else:
            report = self._loader.load(meta.out_dir) if meta.out_dir else build_demo_report()
            ai = {}
            ai_path = meta.out_dir / "ai_report.json" if meta.out_dir else None
            if ai_path and ai_path.exists():
                import json
                try:
                    ai = json.loads(ai_path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    ai = {}
        paper = QFrame()
        paper.setObjectName("paper")
        pv = QVBoxLayout(paper)
        pv.setContentsMargins(24, 20, 24, 20)
        pv.setSpacing(6)

        # 标题 + 编号（对齐设计稿 .report h2 small）
        th = QHBoxLayout()
        title = QLabel("车辆诊断报告")
        title.setObjectName("paperH")
        th.addWidget(title)
        th.addStretch(1)
        no = QLabel(f"编号 {self._paper_no(meta.time)}")
        no.setObjectName("paperNo")
        th.addWidget(no)
        pv.addLayout(th)

        # 车辆信息
        pv.addWidget(self._paper_sec("车辆信息"))
        vi = self._parse_version(report.version)
        for k, v in (("VIN 码", vi.get("vin", "—")),
                     ("车型", vi.get("model", "—")),
                     ("里程", vi.get("mileage", "—")),
                     ("ECU", vi.get("ecu", "—"))):
            pv.addWidget(self._paper_row(k, v))

        # 扫描结果
        pv.addWidget(self._paper_sec("扫描结果"))
        pv.addWidget(self._paper_row("故障总数", f"{len(report.faults)} 个"))
        for f in report.faults:
            pv.addWidget(self._paper_row(f.code, f.desc))

        # AI 分析结论（有 AI 数据时）
        concl = ai.get("overallConclusion")
        if concl:
            pv.addWidget(self._paper_sec("AI 智能分析"))
            c = QLabel(concl)
            c.setObjectName("paperM")
            c.setWordWrap(True)
            pv.addWidget(c)
            for i, d in enumerate(ai.get("diagnosisList", []), start=1):
                line = QLabel(f"{i}. {d.get('faultPoint', '')} —— 可能性 {d.get('probability', '')}")
                line.setObjectName("paperM")
                line.setWordWrap(True)
                pv.addWidget(line)
        if not report.has_data and not concl:
            line = QLabel("（此报告暂无详细数据）")
            line.setObjectName("paperM")
            pv.addWidget(line)

        # 技师签名
        pv.addSpacing(8)
        pv.addWidget(self._paper_row("技师签名", "李翔（认证技师 · 中级）"))
        pv.addWidget(self._paper_row("诊断日期", meta.time))
        self._paper_lay.addWidget(paper)
        if meta.out_dir:
            exp = QPushButton("导出 Markdown")
            exp.setProperty("role", "primary")
            exp.setCursor(Qt.PointingHandCursor)
            exp.clicked.connect(lambda _=False: self._export_markdown(meta))
            self._paper_lay.addWidget(exp)
        self._paper.show()
        self._paper_lay.addStretch(1)

    @staticmethod
    def _paper_sec(title) -> QLabel:
        s = QLabel(title)
        s.setObjectName("paperSec")
        return s

    @staticmethod
    def _paper_row(k, v) -> QFrame:
        r = QFrame()
        r.setObjectName("paperRow")
        h = QHBoxLayout(r)
        h.setContentsMargins(0, 3, 0, 3)
        kk = QLabel(k)
        kk.setObjectName("paperK")
        h.addWidget(kk)
        vv = QLabel(v)
        vv.setObjectName("paperV")
        vv.setWordWrap(True)
        h.addWidget(vv, 1)
        return r

    @staticmethod
    def _paper_no(time_str: str) -> str:
        digits = "".join(ch for ch in (time_str or "") if ch.isdigit())
        if len(digits) >= 12:
            return f"AD-{digits[:8]}-{digits[8:12]}"
        return time_str or "AD-00000000-0000"

    @staticmethod
    def _parse_version(version: str) -> dict:
        info = {"vin": "", "model": "", "mileage": "", "ecu": ""}
        for line in (version or "").splitlines():
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if k == "VIN":
                info["vin"] = v
            elif k == "车型":
                info["model"] = v
            elif k == "里程":
                info["mileage"] = v
            elif k == "ECU":
                info["ecu"] = v
        return info

    def _export_markdown(self, meta):
        md = ["# 智能诊断报告", "", f"- 时间：{meta.time}", f"- 设备：{meta.dev}", ""]
        ai_path = meta.out_dir / "ai_report.json"
        if ai_path.exists():
            import json
            try:
                ai = json.loads(ai_path.read_text(encoding="utf-8", errors="replace"))
                md.append(f"## 结论\n\n{ai.get('overallConclusion', '')}\n")
                for i, d in enumerate(ai.get("diagnosisList", []), start=1):
                    md.append(f"### {i}. {d.get('faultPoint', '')}（{d.get('probability', '')}）\n")
                    md.append(d.get("simpleExplanation", ""))
                    for g in d.get("guideSteps", []):
                        md.append(f"- {g}")
                    md.append("")
            except Exception:
                pass
        try:
            out = meta.out_dir / "report.md"
            out.write_text("\n".join(md), encoding="utf-8")
            self._toast(f"已导出：{out}")
        except Exception as e:
            self._toast(f"导出失败：{e}", "crit")
