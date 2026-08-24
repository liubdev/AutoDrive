"""
AutoDrive Flow 流程引擎
- FlowStep   : 一个可执行步骤（动作 + 验证 + 重试）
- FlowEngine : 顺序执行步骤，事件回调，支持取消

用法:
    from automation.flow.engine import FlowStep, FlowEngine

    engine = FlowEngine()
    engine.steps = build_flow(app)          # list[FlowStep]
    engine.on("step_start", on_step_start)  # 订阅事件
    engine.on("log", on_log)
    engine.run(verify_app=app)              # 阻塞执行，放后台线程
"""

from .engine import (
    FlowEngine,
    FlowStep,
    PENDING,
    RUNNING,
    DONE,
    ERROR,
    CANCELLED,
)

__all__ = [
    "FlowEngine",
    "FlowStep",
    "PENDING",
    "RUNNING",
    "DONE",
    "ERROR",
    "CANCELLED",
]
