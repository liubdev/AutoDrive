"""
DTS 自动控制 - 分步演示

每步操作后页面都会变化，脚本通过等待 + 查找新控件来适应页面变化。

流程:
  1. 启动 DTS → 出现 splash + "确认"按钮
  2. 点击 "确认" → 页面切换
  3. (后续步骤逐步添加)

用法:
  python main.py script scripts/run_dts.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.apps.dts import DtsApp

print("=" * 50)
print("  DTS 自动控制")
print("=" * 50)

app = DtsApp()

# 第1步: 启动 DTS
print("\n[第1步] 启动 DTS...")
if not app.ensure_running(timeout=30):
    print("  ✗ 启动失败")
    exit(1)
print("  ✓ DTS 已启动")

# 第2步: 点击"确认"按钮
print("\n[第2步] 点击'确认'按钮...")
if app.confirm(timeout=15):
    print("  ✓ 已点击确认")
    print("  >> 页面已变化，进入下一界面")
else:
    print("  ✗ 点击确认失败")

# 第3步: 断开连接
print("\n[完成] 断开连接")
app.disconnect()
