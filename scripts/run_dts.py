"""
DTS 自动控制 - 完整数据流保存流程（控制台运行器）

流程定义在 automation/flows/dts_flow.py，这里只是"构建流程 → 用引擎跑"。
GUI (autogui.py) 使用同一份流程定义，行为一致。
"""

import sys
import logging
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="Revert to STA COM threading mode")
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)

from automation.apps.dts import DtsApp
from automation.flow.engine import FlowEngine
from automation.flows.dts_flow import build_dts_flow, make_output_dir


def main():
    log = logging.getLogger("run_dts")
    log.info("=" * 40)
    log.info("  DTS 自动控制")
    log.info("=" * 40)

    # 创建本次执行的输出目录
    out_dir = make_output_dir()
    log.info(f"  输出目录: {out_dir}")

    app = DtsApp()
    engine = FlowEngine()
    engine.steps = build_dts_flow(app, out_dir)

    # 引擎会把所有 Python logging 转发到 log 事件；
    # 控制台输出由上面的 basicConfig 负责，无需额外订阅。
    engine.run(verify_app=app)
    app.disconnect()
    log.info("[完成]")


if __name__ == "__main__":
    main()
