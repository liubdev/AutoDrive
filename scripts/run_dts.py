"""
DTS 自动控制
"""

import sys, logging, warnings, time
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
    log.info("  x 启动失败")
    exit(1)
log.info("  √ DTS 已启动")

log.info("确认弹窗处理")
log.info("[第2步] 点击确认弹窗处理...")
if app.confirm(timeout=15):
    log.info("  √ 已点击确认")
else:
    log.info("  x 点击确认失败")

log.info("[第3步] 一键进入...")
if app.one_click_enter(timeout=15):
    log.info("  √ 已进入")
else:
    log.info("  x 进入失败")

time.sleep(5)
log.info("[第5步] 点击进入系统...")
if app.enter_system(timeout=15):
    log.info("  √ 已点击进入系统")
else:
    log.info("  x 点击进入系统失败")

# 等待数据加载
time.sleep(12)
log.info("[第6步] 通过回车控制发动机系统诊断...")
if app.send_enter(timeout=15):
    log.info("  √ 诊断完成")
else:
    log.info("  x 诊断失败")

# 扫描设备进去到下一步
time.sleep(12)
log.info("[第7步] 通过检车结果发送空格指令进去下一步...")
if app.send_space(timeout=15):
    log.info("  √ 指令发送成功")
else:
    log.info("  x 指令发送失败")

# 发动机2.0
time.sleep(12)
log.info("[第8步] 通过回车控制发动机2.0T 马力L D样件")
if app.send_enter(timeout=15):
    log.info("  √ 诊断完成")
else:
    log.info("  x 诊断失败")

# 系统提示：注意：由于大通厂家设计逻辑原因,.... 第一个空格确认
if app.send_space(timeout=15):
    log.info("  √ 指令发送成功")
else:
    log.info("  x 指令发送失败")
# 等待第二个版本信息出现保存。

path = app.save_info_to_txt("d:/info.txt")  # 指定路径
if path:
    print(f"已保存: {path}")

# 点击空格确认
if app.send_space(timeout=15):
    log.info("  √ 指令发送成功")
else:
    log.info("  x 指令发送失败")

# ── 完成 ──
log.info("")
log.info("[完成] 断开连接")
app.disconnect()
