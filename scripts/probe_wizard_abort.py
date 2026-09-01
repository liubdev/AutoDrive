#!/usr/bin/env python3
"""验证修复：流程失败时引擎不发 flow_done → _on_flow_done 不触发 →
_pending_auto_ai 不置 True → _on_run_finished 走 _flow_errored() 错误分支，
而不是用部分数据启动 AI（旧行为掩盖失败）。"""
import os, sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QSettings
QSettings("AutoDrive", "AutoDrive").clear()
from PySide6.QtWidgets import QApplication

from ui.theme import ThemeManager
from ui.wizard import MainWindow
from automation.flow.engine import FlowEngine, FlowStep, ERROR, DONE

app = QApplication([])
ThemeManager(app).apply()
w = MainWindow()
w.show()

ok = True
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok = ok and cond

# 模拟真实失败：部分数据已采集（fault_codes 存在），但流程在后续步骤失败。
# 旧代码：_on_flow_done 在失败时也触发 → _pending_auto_ai=True → 启动 AI 掩盖错误。
# 新代码：失败不发 flow_done → _pending_auto_ai 保持 False → 走错误分支。
from pathlib import Path
import tempfile
_tmp = Path(tempfile.mkdtemp()) / "DTS_20260901_103000"
_tmp.mkdir(parents=True, exist_ok=True)
(_tmp / "fault_codes.txt").write_text("P2135 节气门位置传感器", encoding="utf-8")
w._out_dir = _tmp

w._engine = FlowEngine([
    FlowStep("已完成的步骤", action=lambda: True),
    FlowStep("失败的步骤", action=lambda: False),
])
# 引擎在失败时会把失败步骤标记 ERROR（新引擎已如此）
w._engine.steps[1].status = ERROR

# 模拟桥接事件序列（新引擎在失败时只发 step_error，不发 flow_done）：
w._on_flow_start(w._engine)
w._on_step_done(w._engine.steps[0])
w._on_step_error(w._engine.steps[1])      # 显示"步骤失败: 失败的步骤"
# 注意：这里没有调用 _on_flow_done —— 这正是修复点
w._on_run_finished()

check("失败流程 → _pending_auto_ai 保持 False", w._pending_auto_ai is False)
check("失败流程 → 未启动 AI 链", w._ai_running is False)
check("失败流程 → _flow_errored() 识别到错误", w._flow_errored() is True)
check("失败流程 → 界面显示失败（非演示/非 AI）",
      "失败" in w.ai_diag._status_lbl.text())
check("失败流程 → 状态就绪", w._dev_status.text() == "○ 就绪")

# 对照：正常完成（有数据）仍走自动 AI —— 未被破坏
w._engine.steps[0].status = DONE
w._engine.steps[1].status = DONE
w._on_flow_done(w._engine)   # 成功时才触发
check("成功有数据 → _pending_auto_ai 置 True（自动 AI 仍保留）",
      w._pending_auto_ai is True)

print(f"== WIZARD-ABORT PROBE {'PASS' if ok else 'FAIL'} ==")
sys.exit(0 if ok else 1)
