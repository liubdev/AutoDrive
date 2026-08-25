"""
AI 诊断知识库：默认知识加载 + 自定义覆盖。

默认知识来自 ai/knowledge/default.json
（由 scripts/build_knowledge.py 从 docs/ 三份 spec 程序化抽取）。
后续支持按车型传入自定义 JSON 覆盖同名项。
"""

import json
import logging
import pathlib
from dataclasses import dataclass, asdict

log = logging.getLogger("autodrive.ai.knowledge")

_KNOWLEDGE_DIR = pathlib.Path(__file__).resolve().parent / "knowledge"
_DEFAULT_PATH = _KNOWLEDGE_DIR / "default.json"

# 静态兜底：default.json 缺失/为空时也要保证基本可用
_FALLBACK = {
    "guide": "",
    "mandatory_streams": "",
    "synonym_dict": "",
    "principle_doc": "",
    "pin_info": "",
    "prompt_content": "",
    "system_principle": "",
    "system_info": "玉柴_EDC17CV44_P1382",
    "subsystems": "",
    "components": "",
    "engine_par": "",
    "typical_cases": "",
}


@dataclass
class DiagnosticKnowledge:
    """AI 三阶段用到的领域知识（全部为纯文本，渲染进模板槽位）"""

    guide: str = ""              # 诊断思路（如动力不足通用提示词）     — stage1
    mandatory_streams: str = ""  # 必选数据流清单                        — stage1
    synonym_dict: str = ""       # 数据流同义词表                        — stage1
    principle_doc: str = ""      # 可定位性判定的「原理文档」             — stage2
    pin_info: str = ""           # ECU/DCU 针脚定义                      — stage3
    prompt_content: str = ""     # 当前现象的诊断思路                    — stage3
    system_principle: str = ""   # 与车辆匹配的原理知识                   — stage3
    system_info: str = ""        # 车辆/ECU/DCU 信息                     — stage1/3
    subsystems: str = ""         # 子系统清单                            — stage3
    components: str = ""         # 部件清单                              — stage3
    engine_par: str = ""         # 发动机参数信息                        — stage3
    typical_cases: str = ""      # 相似典型案例                          — stage3

    def asdict(self) -> dict:
        return asdict(self)


def _normalize(raw: dict) -> dict:
    """缺失/空白的 key 用静态兜底补齐"""
    out = {}
    for key, fallback in _FALLBACK.items():
        val = raw.get(key)
        out[key] = str(val).strip() if isinstance(val, str) and val.strip() else fallback
    return out


def load_default_knowledge() -> DiagnosticKnowledge:
    """加载默认知识库；文件缺失/损坏时回退为仅静态兜底（功能仍可用）"""
    if _DEFAULT_PATH.exists():
        try:
            raw = json.loads(_DEFAULT_PATH.read_text(encoding="utf-8"))
            return DiagnosticKnowledge(**_normalize(raw))
        except Exception as e:  # noqa: BLE001
            log.warning("默认知识库解析失败：%s", e)
    return DiagnosticKnowledge(**_normalize({}))


def load_knowledge(custom_path=None) -> DiagnosticKnowledge:
    """
    加载知识库：默认 + 可选自定义 JSON（自定义非空项覆盖默认）。

    Args:
        custom_path: 自定义知识 JSON 路径（None → 仅默认）。
    """
    base = load_default_knowledge()
    if not custom_path:
        return base
    try:
        raw = json.loads(pathlib.Path(custom_path).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("加载自定义知识库 %s 失败：%s", custom_path, e)
        return base
    merged = base.asdict()
    for key in merged:
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            merged[key] = val.strip()
    return DiagnosticKnowledge(**merged)
