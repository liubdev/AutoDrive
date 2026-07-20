import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.apps.dts import DtsApp

dts = DtsApp()
if dts.ensure_running(timeout=15):
    print("  DTS程序已就绪")
    ss = dts.screenshot()
    if ss:
        print(f"  ✓ 截图: {ss}")
    dts.disconnect()
    print("  ✓ 已断开连接（DTS保持打开）")
else:
    print("  ✗ 启动失败")
