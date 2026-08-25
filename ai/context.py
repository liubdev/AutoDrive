"""
AI 阶段槽位数据组装：把 Report(out_dir) + 用户输入 + 知识库 → 各阶段 `{{slot}}` 字典。

三个模板需要的槽位全部由此产出（模板里没引用的键会被 render 忽略），保证
build_slots 输出一份完整字典即可喂给任意阶段。

CSV 转换：DTS 导出的长表 [参数,值,单位,参考] → spec 期望的转置表（行=参数、列=帧）。
"""

import csv
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("autodrive.ai.context")

# 帧数/参数数上限（控制 prompt 体积；超出部分在表格末尾标注省略）
MAX_PARAMS = 36
MAX_FRAMES = 64
MAX_FILES = 3
MAX_CELLS = 4000

# 清洗：DTS 故障码行 "P0100F9 空气流量计…" 里，code 后的十六进制后缀不属于描述
_HEX_SUFFIX = re.compile(r"^[0-9A-F]{1,2}\s+")

_NOTICE = "（未填写）"


# ── 故障码 ──────────────────────────────────────

def fault_codes_table(report) -> str:
    """Report.faults → markdown 表（对齐 spec：| 故障码 | 故障状态 | 故障描述 |）"""
    rows = []
    for fc in report.faults:
        desc = _HEX_SUFFIX.sub("", fc.desc.strip()).strip()
        status = "严重" if fc.severity == "crit" else "一般"
        rows.append(f"| {fc.code} | {status} | {desc} |")
    if not rows:
        return ""
    header = "| 故障码 | 故障状态 | 故障描述 |\n|---|---|---|"
    return header + "\n" + "\n".join(rows)


# ── 支持的数据流清单 ──────────────────────────────

def supported_stream_set(report) -> set:
    """DataFlow_List_*.txt + CSV 参数名 汇总去重（stage1 的支持清单 + 防幻觉过滤集）"""
    names = set()
    out_dir = getattr(report, "out_dir", None)
    if out_dir:
        for p in sorted(out_dir.glob("DataFlow_List_*.txt")):
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line:
                        names.add(line)
            except Exception as e:
                log.warning("读取 %s 失败: %s", p, e)
    for f in getattr(report, "flows", []):
        if f.name:
            names.add(f.name)
    return names


def supported_streams(report) -> str:
    """支持清单 → JSON 数组字符串（stage1 的 supported_streams_list 槽）"""
    return json.dumps(sorted(supported_stream_set(report)), ensure_ascii=False)


# ── CSV → 转置 markdown 表 ──────────────────────

def _read_long_csv(path: Path) -> list:
    """读取长表 CSV → [(name, value, unit), ...]，跳过表头行"""
    rows = []
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            for r in csv.reader(f):
                if not r:
                    continue
                name = (r[0] or "").strip()
                if not name or name.lower().startswith(("参数", "name", "信号", "项")):
                    continue
                value = r[1].strip() if len(r) > 1 else ""
                unit = r[2].strip() if len(r) > 2 else ""
                rows.append((name, value, unit))
    except Exception as e:
        log.warning("读取 CSV %s 失败: %s", path, e)
    return rows


def _pivot(rows: list) -> str:
    """长表 → 转置表 markdown。参数名(单位) 为行，帧1..N 为列。"""
    names, frames = [], {}
    for name, value, unit in rows:
        if name not in frames:
            frames[name] = []
            names.append(name)
        frames[name].append(value)

    if len(names) > MAX_PARAMS:
        names = names[:MAX_PARAMS]
    truncated_params = len(names) < len(frames)

    # 每参数最多 MAX_FRAMES 帧（截断后续）
    n_frames = 0
    body = []
    for name in names:
        vals = frames[name][:MAX_FRAMES]
        n_frames = max(n_frames, len(vals))
        unit = _unit_of(rows, name)
        label = f"{name}({unit})" if unit else name
        cells = " | ".join(vals)
        body.append(f"| {label} | {cells} |")
    n_frames = min(n_frames, MAX_FRAMES)

    header = "| 参数 | " + " | ".join(f"帧{i+1}" for i in range(n_frames)) + " |"
    sep = "|---|" + "|---|" * n_frames
    table = header + "\n" + sep + "\n" + "\n".join(body)
    notes = []
    if truncated_params:
        notes.append(f"（参数过多，仅列前 {MAX_PARAMS} 项）")
    if n_frames == MAX_FRAMES:
        notes.append(f"（每参数仅列前 {MAX_FRAMES} 帧）")
    return table + ("\n" + "，".join(notes) if notes else "")


def _unit_of(rows: list, name: str) -> str:
    for n, _, unit in rows:
        if n == name and unit:
            return unit
    return ""


def csv_to_markdown(out_dir) -> str:
    """out_dir 下所有 DataFlow_*.csv → 分段转置表。无 CSV 返回空串。"""
    if not out_dir:
        return ""
    sections, cells, files = [], 0, 0
    for p in sorted(out_dir.glob("DataFlow_*.csv")):
        if p.name.lower().startswith("dataflow_"):
            rows = _read_long_csv(p)
            if not rows:
                continue
            files += 1
            if files > MAX_FILES:
                break
            section = f"### 数据流{files}\n\n{_pivot(rows)}"
            cells += len(rows)
            sections.append(section)
            if cells >= MAX_CELLS:
                sections.append("（数据量过大，后续数据流文件省略，见输出目录）")
                break
    if not sections:
        return ""
    return "\n\n".join(sections)


# ── 各阶段槽位字典 ──────────────────────────────

def build_slots(report, symptom: str, notes: str, knowledge=None,
                stage_results: dict = None) -> dict:
    """
    组装覆盖三个模板全部 `{{slot}}` 的字典。

    Args:
        report: ui.report.Report（out_dir / faults / flows）
        symptom: 用户填写的故障现象
        notes: 用户补充说明
        knowledge: DiagnosticKnowledge（或 None → 默认）
        stage_results: {"plan": CollectionPlan, "locatability": Locatability}
                       前一阶段输出（可选，供阶段3引用）
    """
    if knowledge is None:
        from ai.knowledge import load_default_knowledge
        knowledge = load_default_knowledge()
    k = knowledge.asdict()
    results = stage_results or {}
    plan = results.get("plan")
    loc = results.get("locatability")

    symptom = (symptom or "").strip() or _NOTICE
    notes = (notes or "").strip()

    engine_tbl = fault_codes_table(report)
    csv_txt = csv_to_markdown(getattr(report, "out_dir", None))
    supported = supported_streams(report)

    # 阶段2/3 的定位判断描述
    if loc is not None:
        verdict = "原地数据足以定位故障，无需路试" if loc.is_locatable else "原地数据不足，需要路试或在特定工况下复测"
        result_analysis = f"{verdict}：{loc.reason}"
        root_cause = loc.reason
    else:
        result_analysis = _NOTICE
        root_cause = _NOTICE
    working_conditions = (plan.working_conditions if plan else "") or _NOTICE

    return {
        # 用户输入
        "fault_phenomenon": symptom,
        "symptom": symptom,
        "user_description": notes,
        "user_notes": notes,

        # 故障码
        "engine_fault_codes": engine_tbl,
        "after_treatment_fault_codes": "",

        # 数据流
        "supported_streams_list": supported,
        "actual_data_csv": csv_txt,
        "csv_content": csv_txt,

        # 未安装部件（暂由补充说明承载，后续可独立成字段）
        "uninstalled_components": "",
        "uninstalled_parts": "",

        # 阶段2/3 中间结果
        "result_analysis": result_analysis,
        "root_cause_analysis": root_cause,
        "data_stream_status": working_conditions,
        "working_conditions": working_conditions,

        # 车辆信息
        "system_info": k["system_info"],
        "enginepar_info": k["engine_par"],
        "target_subsystems": k["subsystems"],
        "target_components": k["components"],

        # 知识库
        "diagnostic_guide": k["guide"],
        "mandatory_list": k["mandatory_streams"],
        "synonym_dictionary": k["synonym_dict"],
        "principle_doc": k["principle_doc"],
        "pin_info": k["pin_info"],
        "prompt_content": k["prompt_content"],
        "system_principle": k["system_principle"],
        "typical_cases": k["typical_cases"],
    }
