"""
DTS 自动控制
"""

import sys, logging, warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("run_dts")

from automation.apps.dts import DtsApp

# ── 第1步: 启动 ──
log.info("=" * 40)
log.info("  DTS 自动控制")
log.info("=" * 40)
log.info("")
log.info("[第1步] 启动 DTS...")

app = DtsApp()
if not app.ensure_running(timeout=30):
    log.info("  ✗ 启动失败")
    exit(1)
log.info("  ✓ DTS 已启动")

# ── 第2步: 确认 ──
log.info("")
log.info("[第2步] 点击确认...")
if app.confirm(timeout=15):
    log.info("  ✓ 已点击确认")
else:
    log.info("  ✗ 点击确认失败")

# ── 第3步: 一键进入 ──
import time

log.info("")
log.info("[第3步] 一键进入...")
if app.one_click_enter(timeout=15):
    log.info("  ✓ 已进入")
else:
    log.info("  ✗ 进入失败")

# ── 第4步: 发动机诊断 ──
time.sleep(10)
log.info("")
log.info("[第4步] 发动机系统诊断...")
if app.diagnose_engine_system(timeout=15):
    log.info("  ✓ 诊断完成")
else:
    log.info("  ✗ 诊断失败")

# ── 第5步: 点击进入系统 ──
time.sleep(5)
log.info("[第5步] 点击进入系统...")
if app.enter_system(timeout=15):
    log.info("  ✓ 已点击进入系统")
else:
    log.info("  ✗ 点击进入系统失败")

# ── 第6步: 发动机系统诊断  ──
# time.sleep(12)
# log.info("[第6步] 发动机系统诊断...")
# if app.diagnose_engine_system(timeout=15):
#     log.info("  ✓ 诊断完成")
# else:
#     log.info("  ✗ 诊断失败")

# ── 完成 ──
log.info("")
log.info("[完成] 断开连接")
app.disconnect()
