#!/usr/bin/env python3
"""验证引擎严格顺序：上一步未结束（失败/顺序违反）→ 抛 FlowStepError + flow_error 事件，
停止继续执行，绝不发 flow_done；正常完成仍发 flow_done。"""
import os, sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.flow.engine import FlowEngine, FlowStep, FlowStepError, DONE, PENDING, ERROR

ok = True
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok = ok and cond

def make_engine(steps):
    eng = FlowEngine(steps)
    ev = {"flow_error": [], "flow_done": [], "flow_cancelled": [], "step_error": []}
    eng.on("flow_error", lambda e: ev["flow_error"].append(e))
    eng.on("flow_done", lambda e: ev["flow_done"].append(e))
    eng.on("flow_cancelled", lambda e: ev["flow_cancelled"].append(e))
    eng.on("step_error", lambda s: ev["step_error"].append(s))
    return eng, ev

# ── 1. 步骤动作失败 → 抛异常 + flow_error，不发 flow_done，下一步不执行 ──
eng, ev = make_engine([
    FlowStep("第一步", action=lambda: False),          # 动作失败
    FlowStep("第二步", action=lambda: True),
])
raised = None
try:
    eng.run()
except FlowStepError as e:
    raised = e
check("1. 动作失败 → run() 抛出 FlowStepError", raised is not None)
check("1. 发 flow_error 事件", len(ev["flow_error"]) == 1)
check("1. 不发 flow_done（不当作自然完成）", len(ev["flow_done"]) == 0)
check("1. 第一步标记 ERROR", eng.steps[0].status == ERROR)
check("1. 第二步未执行（保持 PENDING）", eng.steps[1].status == PENDING)
check("1. 失败步骤被当作中止原因", raised is not None and "执行失败" in str(raised))

# ── 2. 验证未通过（非 continue_on_missing）→ 同样中止 ──
class FakeVerifyApp:
    def wait_for_control(self, *a, **k):
        return False

eng, ev = make_engine([
    FlowStep("验证步", action=lambda: True,
             verify={"auto_id": "X", "control_type": "Button"}, retry=1, timeout=1),
    FlowStep("后续步", action=lambda: True),
])
raised = None
try:
    eng.run(verify_app=FakeVerifyApp())
except FlowStepError as e:
    raised = e
check("2. 验证未通过 → 抛 FlowStepError", raised is not None)
check("2. 发 flow_error 不发 flow_done",
      len(ev["flow_error"]) == 1 and len(ev["flow_done"]) == 0)
check("2. 后续步未执行", eng.steps[1].status == PENDING)

# ── 3. 正常完成 → flow_done，不抛异常 ──
eng, ev = make_engine([
    FlowStep("A", action=lambda: True),
    FlowStep("B", action=lambda: True),
])
raised = None
try:
    eng.run()
except FlowStepError as e:
    raised = e
check("3. 正常完成不抛异常", raised is None)
check("3. 发 flow_done", len(ev["flow_done"]) == 1 and len(ev["flow_error"]) == 0)
check("3. 全部 DONE", all(s.status == DONE for s in eng.steps))

# ── 4. 顺序守卫：上一步未 DONE 就试图下一步 → 抛异常 ──
# 模拟 _run_step"返回成功却没把状态置 DONE"（任何回归都逃不掉守卫）
orig = FlowEngine._run_step
FlowEngine._run_step = lambda self, step, verify_app: True   # 不设 status
eng, ev = make_engine([
    FlowStep("上一步", action=lambda: True),
    FlowStep("下一步", action=lambda: True),
])
raised = None
try:
    eng.run()
except FlowStepError as e:
    raised = e
FlowEngine._run_step = orig
check("4. 上一步未完成 → 抛 FlowStepError", raised is not None)
check("4. 异常信息含 未完成/上一步", raised is not None and "未完成" in str(raised))
check("4. 未发 flow_done", len(ev["flow_done"]) == 0)

# ── 5. 取消仍走取消语义（不抛异常） ──
# run() 开头会 clear 取消事件，故在步骤动作内触发"运行中取消"
eng, ev = make_engine([FlowStep("A", action=lambda: True),
                       FlowStep("B", action=lambda: True)])
eng.steps[0].action = lambda: (eng.cancel() or True)
raised = None
try:
    eng.run()
except FlowStepError as e:
    raised = e
check("5. 取消 → 不抛异常，发 flow_cancelled",
      raised is None and len(ev["flow_cancelled"]) == 1 and len(ev["flow_done"]) == 0)

print(f"== FLOW-ORDER PROBE {'PASS' if ok else 'FAIL'} ==")
sys.exit(0 if ok else 1)
