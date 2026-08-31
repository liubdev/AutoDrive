"""
输出目录解析：把一次运行保存下来的文件整理成界面数据。

约定输出目录结构（由 automation/flows/dts_flow.py 生成）:
  version_info.txt        版本信息文本
  fault_codes.txt         故障码（每行一条，含代码与描述）
  DataFlow_List_N.txt     数据流参数列表（N=1,2,...）
  *.csv                   数据流导出（若 DTS 导出成功）

容错：任一文件缺失/损坏都不影响其余数据的展示。
"""

import csv
import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("autodrive.ui.report")

# P 码 4 位可为十六进制（真实样本 P009B/P21C7/P203F…），子码段如 F9/13 由描述清洗处理
DTC_RE = re.compile(r"[PBCU][0-9A-F]{4}")

# 轻量严重度推断：命中这些关键词判"严重"，否则"一般"
_CRIT_KEYWORDS = ("失火", "爆震", "停缸", "断油", "ecu", "安全")


@dataclass
class FaultCode:
    code: str
    desc: str = ""
    severity: str = "warn"      # warn=一般 / crit=严重


@dataclass
class DataFlowItem:
    name: str
    value: str = ""
    unit: str = ""
    ref: str = ""
    status: str = ""            # ok / warn / crit / "" 未知
    status_text: str = ""       # 正常 / 偏高 / 异常


@dataclass
class SavedFile:
    name: str
    size: int = 0
    path: Path = None


@dataclass
class Report:
    out_dir: Path = None
    version: str = ""
    faults: list = field(default_factory=list)
    flows: list = field(default_factory=list)
    files: list = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.faults or self.flows or self.files)


class ReportLoader:
    """从输出目录构建 Report"""

    def load(self, out_dir: Path) -> Report:
        report = Report(out_dir=out_dir)
        if not out_dir or not out_dir.is_dir():
            return report

        report.version = self._read_version(out_dir)
        report.faults = self._parse_faults(out_dir / "fault_codes.txt")
        report.flows = self._parse_flows(out_dir)
        report.files = self._list_files(out_dir)
        return report

    def _read_version(self, out_dir: Path) -> str:
        try:
            p = out_dir / "version_info.txt"
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as e:
            log.warning("read version failed: %s", e)
        return ""

    def _parse_faults(self, path: Path) -> list:
        faults = []
        try:
            if not path.exists():
                return faults
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                m = DTC_RE.search(line)
                code = m.group(0) if m else ""
                desc = line[m.end():].strip(" :\t-") if m else line
                if not code:
                    continue
                sev = "crit" if any(k in desc.lower() for k in _CRIT_KEYWORDS) else "warn"
                faults.append(FaultCode(code=code, desc=desc, severity=sev))
        except Exception as e:
            log.warning("parse faults failed: %s", e)
        return faults

    def _parse_flows(self, out_dir: Path) -> list:
        flows = []
        try:
            csv_path = next(out_dir.glob("*.csv"), None)
            if csv_path and csv_path.stat().st_size > 0:
                flows = self._parse_csv(csv_path)
            if flows:
                return flows
            # 无可用 CSV：退回参数列表文件（只有名称）
            for p in sorted(out_dir.glob("DataFlow_List_*.txt")):
                for name in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    name = name.strip()
                    if name and not any(f.name == name for f in flows):
                        flows.append(DataFlowItem(name=name))
        except Exception as e:
            log.warning("parse flows failed: %s", e)
        return flows

    def _parse_csv(self, path: Path) -> list:
        items = []
        try:
            with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
                for row in csv.reader(f):
                    if not row:
                        continue
                    name = (row[0] or "").strip()
                    if not name or name.lower().startswith(("参数", "name", "信号")):
                        continue
                    value = row[1].strip() if len(row) > 1 else ""
                    unit = row[2].strip() if len(row) > 2 else ""
                    ref = row[3].strip() if len(row) > 3 else ""
                    items.append(DataFlowItem(name=name, value=value, unit=unit, ref=ref))
        except Exception as e:
            log.warning("parse csv failed: %s", e)
            return []
        return items

    def _list_files(self, out_dir: Path) -> list:
        files = []
        try:
            for p in sorted(out_dir.iterdir()):
                if p.is_file():
                    files.append(SavedFile(name=p.name, size=p.stat().st_size, path=p))
        except Exception as e:
            log.warning("list files failed: %s", e)
        return files


# ═══════════════════════════════════════════════════════════
#  ReportMeta / ReportStore —— 报告列表（诊断报告页）
# ═══════════════════════════════════════════════════════════

from config.settings import settings  # noqa: E402 —— 仅用 reports_dir（非敏感字段）

_REPORT_DIR_RE = re.compile(r"DTS_(\d{8})_(\d{6})")


@dataclass
class ReportMeta:
    time: str               # "2026-08-25 16:28"
    dev: str = "DTS"
    summary: str = ""
    out_dir: Path = None
    dir_name: str = ""


class ReportStore:
    """扫描 settings.reports_dir 下 DTS_YYYYMMDD_HHMMSS 目录。

    time 由目录名解析：DTS_20260825_162859 → "2026-08-25 16:28"。
    summary 优先取 ai_report.json 的 overallConclusion，回退故障码首行。
    """

    def __init__(self, base: Path = None):
        self.base = base or settings.reports_dir

    def list_reports(self) -> list:
        metas = []
        if not self.base or not self.base.is_dir():
            return metas
        for d in sorted(self.base.iterdir()):
            if not d.is_dir():
                continue
            m = _REPORT_DIR_RE.match(d.name)
            if not m:
                continue
            date, t = m.group(1), m.group(2)
            fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]} {t[:2]}:{t[2:4]}"
            metas.append(ReportMeta(time=fmt, out_dir=d, dir_name=d.name,
                                    summary=self._summary(d)))
        metas.sort(key=lambda r: r.time, reverse=True)
        return metas

    def _summary(self, out_dir: Path) -> str:
        ai = out_dir / "ai_report.json"
        try:
            if ai.exists():
                data = json.loads(ai.read_text(encoding="utf-8", errors="replace"))
                s = (data.get("overallConclusion") or "").strip()
                if s:
                    return s
        except Exception as e:
            log.warning("read ai_report summary failed: %s", e)
        fc = out_dir / "fault_codes.txt"
        try:
            if fc.exists():
                lines = [l.strip() for l in fc.read_text(encoding="utf-8", errors="replace")
                         .splitlines() if l.strip()]
                if lines:
                    return "；".join(lines[:2])
        except Exception as e:
            log.warning("read fault summary failed: %s", e)
        return ""

    def delete(self, meta) -> bool:
        try:
            if meta.out_dir and meta.out_dir.is_dir():
                shutil.rmtree(meta.out_dir)
                return True
        except Exception as e:
            log.warning("delete report failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════════
#  演示数据（无真机 / 无报告时降级填充）
# ═══════════════════════════════════════════════════════════

def build_demo_report() -> Report:
    """从 ui.lcsdata 构造演示 Report（AI 诊断页降级用）。"""
    from ui.lcsdata import DEMO_FAULTS, DEMO_VEHICLE
    rep = Report(out_dir=None)
    rep.version = "\n".join([
        f"VIN: {DEMO_VEHICLE['vin']}",
        f"车型: {DEMO_VEHICLE['model']}",
        f"里程: {DEMO_VEHICLE['mileage']}",
        f"ECU: {DEMO_VEHICLE['ecu']}",
    ])
    for f in DEMO_FAULTS:
        rep.faults.append(FaultCode(code=f["code"], desc=f["desc"],
                                    severity="crit" if f["status"] == "cur" else "warn"))
    return rep


def build_demo_ai_report() -> dict:
    from ui.lcsdata import DEMO_AI_REPORT
    return dict(DEMO_AI_REPORT)
