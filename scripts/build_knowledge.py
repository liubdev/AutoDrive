#!/usr/bin/env python3
"""从 docs/ 下三份 AI spec 抽取默认知识库 → ai/knowledge/default.json

知识源（docs 为唯一事实来源，本脚本输出为派生物，改 docs 后重跑本脚本即可）：
  - AI确认采集列表.txt : 诊断思路(id=365) / 必选数据流(id=327) / 同义词表(id=214)
  - 是否需要路试.txt    : 判定原理文档(id=515)
  - 输出维修报告.txt    : 针脚定义(id=33) / 诊断思路(id=514)
                         / 燃油系统原理(480,218,219,155,553) / 电路排查技巧(58)

用法: python scripts/build_knowledge.py
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / "ai" / "knowledge" / "default.json"

# 与「动力不足 / P2135 / 玉柴EDC17CV44」demo 匹配的原理白名单
PRINCIPLE_WHITELIST = {"480", "218", "219", "155", "553", "58"}

# spec 示例中的车辆信息（保持默认值一致）
SYSTEM_INFO = (
    "玉柴_EDC17CV44_P1382 (ECU: 发动机系统(柴油)/博世/EDC17CV44, "
    "DCU: {\"ecuNo\":\"玉柴三立DCU\",\"eng\":\"\",\"module\":\"后处理系统\","
    "\"systemId\":\"SYSTEM_001294\",\"systemName\":\"三立_后处理\"})"
)


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _extract(text: str, tag: str, id_: str) -> str:
    """抽取 <tag ... id="ID" ...>...</tag> 块并去公共缩进。"""
    m = re.search(
        rf"<{tag}\b[^>]*id=\"{id_}\"[^>]*>(.*?)</{tag}>",
        text,
        re.S,
    )
    if not m:
        raise SystemExit(f"未找到 <{tag} id=\"{id_}\"> 块")
    return _dedent(m.group(1))


def _dedent(text: str) -> str:
    lines = text.strip("\n").splitlines()
    indents = [len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()]
    common = min(indents) if indents else 0
    return "\n".join(
        ln[common:] if ln.strip() else "" for ln in lines
    ).strip()


def _extract_principles(text: str, ids) -> list:
    out = []
    for id_ in sorted(ids, key=lambda x: int(x)):
        m = re.search(
            rf"<principle\b[^>]*id=\"{id_}\"[^>]*>(.*?)</principle>",
            text,
            re.S,
        )
        if m:
            out.append(f"【原理{id_}】\n{_dedent(m.group(1))}")
    return out


def main():
    collect = _read("AI确认采集列表.txt")
    roadtest = _read("是否需要路试.txt")
    report = _read("输出维修报告.txt")

    knowledge = {
        # stage1
        "guide": _extract(collect, "prompt_knowledge", "365"),
        "mandatory_streams": _extract(collect, "dataflow", "327"),
        "synonym_dict": _extract(collect, "synonym_streams", "214"),
        # stage2
        "principle_doc": _extract(roadtest, "prompt_knowledge", "515"),
        # stage3
        "pin_info": _extract(report, "pin_info", "33"),
        "prompt_content": _extract(report, "prompt_knowledge", "514"),
        "system_principle": "\n\n".join(
            _extract_principles(report, PRINCIPLE_WHITELIST)
        ),
        # 静态兜底（与 spec 示例一致）
        "system_info": SYSTEM_INFO,
        "subsystems": "进气预热系统\n燃油系统\n进气系统",
        "components": "冷却液温度传感器\n燃油计量单元(IMV)\n燃油轨压传感器(FRP)",
        "engine_par": "",
        "typical_cases": "",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(knowledge, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for k, v in knowledge.items():
        print(f"{k}: {len(v)} chars")
    print(f"\n→ {OUT}")


if __name__ == "__main__":
    main()
