"""
AI 三阶段诊断编排。

stage1  采集计划   AI 确认采集哪些数据流 + 采集工况        → CollectionPlan
stage2  路试判断   原地数据能否定位问题，是否需要路试      → Locatability
stage3  维修报告   汇总输出结构化排查报告                   → dict(overallConclusion + diagnosisList)

run_full 顺序跑三段，把每段结果持久化到 out_dir（供 AI 页重看/刷新）。
解析器对模型输出做容错：容忍 ```json 围栏、前后多余文本、布尔变体。
"""

import json
import logging
import pathlib
from dataclasses import dataclass, field, asdict

from ai.deepseek import AiError, DeepSeekClient
from ai.prompts import build_messages
from ai.knowledge import load_knowledge, DiagnosticKnowledge

log = logging.getLogger("autodrive.ai.chain")


# ── 结果类型 ────────────────────────────────────


@dataclass
class CollectionPlan:
    streams: list = field(default_factory=list)
    working_conditions: str = ""
    raw: str = ""

    def asdict(self) -> dict:
        return asdict(self)


@dataclass
class Locatability:
    is_locatable: bool = False
    reason: str = ""
    raw: str = ""

    def asdict(self) -> dict:
        return asdict(self)


# ── 容错解析 ────────────────────────────────────


def extract_json(text: str) -> dict:
    """从模型输出中稳健提取 JSON 对象。

    容忍：```json 围栏、开头的 json 标识、前后多余文本、对象内嵌套花括号。
    找不到完整对象抛 AiError。
    """
    text = (text or "").strip()
    # 去掉 markdown 围栏
    if text.startswith("```"):
        lines = text.splitlines()
        body = "\n".join(lines[1:])
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
        text = body.strip()
    if text.lower().startswith("json"):
        text = text[4:].lstrip()

    start = text.find("{")
    if start == -1:
        raise AiError("AI 输出中未找到 JSON 对象")

    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    raise AiError(f"AI 输出 JSON 解析失败：{e}") from e
    raise AiError("AI 输出 JSON 不完整")


def _as_bool(v) -> bool:
    """布尔变体容错：true/false/是/否/可/不可..."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "1", "是", "能", "可", "可以"):
            return True
        if s in ("false", "no", "0", "否", "不能", "不可", "不可以"):
            return False
    return bool(v)


# ── 编排 ────────────────────────────────────────


class AiDiagnosticChain:
    def __init__(self, client=None, knowledge=None):
        self.client = client or DeepSeekClient()
        self.knowledge: DiagnosticKnowledge = knowledge or load_knowledge()

    # -- 单阶段 --------------------------------------------------

    def stage1_collection_plan(self, slots: dict, report=None) -> CollectionPlan:
        """阶段1：确认采集列表。streams 会做防幻觉过滤（只保留支持清单中的项）。"""
        messages = build_messages(1, slots)
        text = self.client.chat(messages)
        try:
            parsed = extract_json(text)
        except AiError:
            log.warning("stage1 输出非 JSON，原文：%s", text[:300])
            raise

        streams = [str(s).strip() for s in (parsed.get("streams") or [])]
        supported = None
        if report is not None:
            from ai.context import supported_stream_set

            supported = supported_stream_set(report)
        if supported:
            bad = [s for s in streams if s not in supported]
            streams = [s for s in streams if s in supported]
            if bad:
                log.info(
                    "stage1 过滤 %d 个不在支持清单中的数据流：%s", len(bad), bad[:10]
                )
        return CollectionPlan(
            streams=streams,
            working_conditions=str(parsed.get("working_conditions") or ""),
            raw=text,
        )

    def stage2_locatability(self, slots: dict) -> Locatability:
        """阶段2：原地数据能否定位，是否需要路试。"""
        messages = build_messages(2, slots)
        text = self.client.chat(messages)
        try:
            parsed = extract_json(text)
        except AiError:
            log.warning("stage2 输出非 JSON，原文：%s", text[:300])
            raise
        return Locatability(
            is_locatable=_as_bool(parsed.get("is_locatable")),
            reason=str(parsed.get("reason") or ""),
            raw=text,
        )

    def stage3_report(self, slots: dict) -> dict:
        """阶段3：结构化维修报告。返回 {"overallConclusion", "diagnosisList"}。"""
        messages = build_messages(3, slots)
        text = self.client.chat(messages)
        try:
            parsed = extract_json(text)
        except AiError:
            log.warning("stage3 输出非 JSON，原文：%s", text[:300])
            raise
        return {
            "overallConclusion": str(parsed.get("overallConclusion") or ""),
            "diagnosisList": parsed.get("diagnosisList") or [],
            "raw": text,
        }

    # -- 全链路 --------------------------------------------------

    def run_full(
        self,
        report,
        symptom: str,
        notes: str = "",
        out_dir=None,
        callbacks: dict = None,
    ) -> dict:
        """
        顺序执行三阶段，结果持久化到 out_dir。

        Args:
            report: ui.report.Report
            symptom: 故障现象
            notes: 补充说明
            out_dir: 输出目录（默认 report.out_dir；为空则只跑不落盘）
            callbacks: {"stage_start": fn(stage_no, name),
                        "stage_done": fn(stage_no, name, obj)}

        Returns:
            {"plan": CollectionPlan, "locatability": Locatability,
             "report": dict, "out_dir": Path|None}
        """
        cb = callbacks or {}
        from ai.context import build_slots

        out_dir = out_dir or getattr(report, "out_dir", None)
        slots = build_slots(report, symptom, notes, self.knowledge)

        def start(no, name):
            if cb.get("stage_start"):
                cb["stage_start"](no, name)

        def done(no, name, obj):
            if cb.get("stage_done"):
                cb["stage_done"](no, name, obj)

        # 阶段1
        start(1, "确认采集列表")
        plan = self.stage1_collection_plan(slots, report=report)
        done(1, "确认采集列表", plan)

        # 阶段2（注入阶段1的工况作为参考）
        slots2 = dict(slots)
        slots2["working_conditions"] = plan.working_conditions
        start(2, "是否需要路试")
        loc = self.stage2_locatability(slots2)
        done(2, "是否需要路试", loc)

        # 阶段3（注入阶段1/2 的中间结果）
        slots3 = dict(slots2)
        verdict = (
            "原地数据足以定位故障，无需路试"
            if loc.is_locatable
            else "原地数据不足，需要路试或在特定工况下复测"
        )
        slots3["result_analysis"] = f"{verdict}：{loc.reason}"
        slots3["root_cause_analysis"] = loc.reason
        slots3["data_stream_status"] = plan.working_conditions
        start(3, "输出维修报告")
        report_data = self.stage3_report(slots3)
        done(3, "输出维修报告", report_data)

        if out_dir:
            self._persist(out_dir, plan, loc, report_data)

        return {
            "plan": plan,
            "locatability": loc,
            "report": report_data,
            "out_dir": out_dir,
        }

    @staticmethod
    def _persist(out_dir, plan, loc, report_data):
        """把三段结果写入 out_dir（AI 页 load_from 据此恢复）。"""
        out_dir = pathlib.Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "ai_collection_plan.json": json.dumps(
                {
                    "streams": plan.streams,
                    "working_conditions": plan.working_conditions,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "ai_locatability.json": json.dumps(
                {"is_locatable": loc.is_locatable, "reason": loc.reason},
                ensure_ascii=False,
                indent=2,
            ),
            "ai_report.json": json.dumps(
                {
                    "overallConclusion": report_data.get("overallConclusion", ""),
                    "diagnosisList": report_data.get("diagnosisList", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
        }
        for name, content in files.items():
            try:
                (out_dir / name).write_text(content, encoding="utf-8")
                log.info("✓ AI 结果已保存: %s", out_dir / name)
            except Exception as e:  # noqa: BLE001
                log.warning("保存 %s 失败: %s", name, e)
