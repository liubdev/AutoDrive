"""
测试：点击"向右翻页"按钮
"""

import sys, logging, warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)

from automation.apps.dts import DtsApp

app = DtsApp()
if not app.ensure_running(timeout=30):
    print("  ✗ DTS 未启动")
    exit(1)
app._reconnect_main(timeout=10)

btn = app.window.child_window(
    auto_id="DownButton", control_type="Button", found_index=0
)
if btn.exists(timeout=3):
    for i in range(5):
        btn.click()
        print(f"  ✓ 第{i+1}次点击向右翻页")
        import time

        time.sleep(0.5)

app.disconnect()
