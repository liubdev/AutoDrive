"""仅测试 DTS 最后一步，不结束或重启已有 DTS 进程。

运行前请手动把 DTS 停留在数据流列表页面，并确保当前数据流可见。
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.apps.dts import DtsApp
from automation.flows.dts_flow import (
    _data_flow_loop,
    close_run_log,
    make_output_dir,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="只测试 DTS 数据流循环，不重启 DTS")
    parser.add_argument(
        "--max-flows", type=int, default=1, help="最多处理的数据流数量，默认 1"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    log = logging.getLogger("run_dts_last_step")
    if args.max_flows < 1:
        log.error("--max-flows 必须大于 0")
        return 2

    app = DtsApp()
    if not app.connect_existing():
        log.error("未找到正在运行的 DTS，请先手动启动并停留在数据流页面")
        return 1

    out_dir = make_output_dir()
    app.run_output_dir = out_dir
    log.info("只执行最后一步，DTS 进程保持不变")
    log.info("输出目录: %s", out_dir)
    try:
        return 0 if _data_flow_loop(app, out_dir, args.max_flows) else 1
    finally:
        app.disconnect()
        close_run_log()


if __name__ == "__main__":
    raise SystemExit(main())
