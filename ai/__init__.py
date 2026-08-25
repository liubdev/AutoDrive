"""
AutoDrive AI 诊断包。

纯标准库实现（urllib 调 DeepSeek API），不引入第三方依赖：
  deepseek  DeepSeek 客户端（OpenAI 兼容）
  prompts   提示词模板加载 / {{slot}} 渲染
  context   槽位数据组装（Report + 用户输入 + 知识库 → 槽位字典）
  chain     AiDiagnosticChain 三阶段编排
  knowledge 默认/自定义知识库加载
"""

from ai.deepseek import AiError, DeepSeekClient
from ai.chain import AiDiagnosticChain, CollectionPlan, Locatability
from ai.knowledge import DiagnosticKnowledge, load_knowledge, load_default_knowledge

__all__ = [
    "AiError",
    "DeepSeekClient",
    "AiDiagnosticChain",
    "CollectionPlan",
    "Locatability",
    "DiagnosticKnowledge",
    "load_knowledge",
    "load_default_knowledge",
]
