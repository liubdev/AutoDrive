"""
提示词模板加载与渲染。

模板文件：ai/templates/stage{1,2,3}_*.txt（三份 spec 的槽位化副本，指令文字逐字保留，
示例数据替换为 {{slot}} 标记；输出格式指令已内嵌在模板 <output_format>/<output_rules> 中）。

渲染：`{{key}}` → data[key]；模板中残留的未提供槽位 → 空串（防止占位符泄漏给模型）。
"""

import logging
import pathlib
import re

log = logging.getLogger("autodrive.ai.prompts")

_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent / "templates"
_TEMPLATE_FILES = {
    1: "stage1_collect.txt",
    2: "stage2_roadtest.txt",
    3: "stage3_report.txt",
}

# 兜底：把没被 data 覆盖的 {{slot}} 清掉
_LEFTOVER = re.compile(r"\{\{[a-z_][a-z0-9_]*\}\}")

_cache: dict = {}


def load_template(stage: int) -> str:
    """加载并缓存指定阶段模板文本。"""
    if stage not in _cache:
        path = _TEMPLATE_DIR / _TEMPLATE_FILES[stage]
        try:
            _cache[stage] = path.read_text(encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"提示词模板加载失败: {path}") from e
    return _cache[stage]


def render(stage: int, data: dict) -> str:
    """把 data 渲染进模板；缺失槽位 → 空串。"""
    tpl = load_template(stage)
    for key, val in data.items():
        tpl = tpl.replace("{{" + key + "}}", val)
    return _LEFTOVER.sub("", tpl)


def build_messages(stage: int, data: dict) -> list:
    """构造 OpenAI 兼容 messages：system=渲染后模板，user=简短指令。"""
    system = render(stage, data)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "请严格按照上述系统要求执行，直接输出结果。"},
    ]
