#!/usr/bin/env python3
"""GUI 冒烟：offscreen 平台实例化 MainWindow，走一遍 AI 页交互与信号链路。

用法: python scripts/test_gui_smoke.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS, FAIL = 0, 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def main():
    from PySide6.QtWidgets import QApplication
    from ui.report import ReportLoader
    from ui.wizard import MainWindow
    from ai.chain import CollectionPlan, Locatability

    # 夹具 out_dir
    tmp = Path(tempfile.mkdtemp(prefix="ai_gui_"))
    (tmp / "fault_codes.txt").write_text(
        "P2135 节气门位置传感器电压相关性故障\n", encoding="utf-8")
    (tmp / "DataFlow_List_1.txt").write_text(
        "发动机转速\n共轨压力\n车速\n", encoding="utf-8")
    (tmp / "DataFlow_1.csv").write_text(
        "参数,值,单位,参考范围\n"
        "发动机转速,750,r/min,650-850\n"
        "共轨压力,320,bar,250-400\n", encoding="utf-8")

    app = QApplication([])
    w = MainWindow()

    # 1. set_report → 按钮可用 + 数据计数
    w._out_dir = tmp
    report = ReportLoader().load(tmp)
    w.pages.ai.set_report(report)
    ok("报告加载后按钮可用", w.pages.ai._run_btn.isEnabled())
    ok("数据计数显示", "1 条故障码" in w.pages.ai._sum_lbl.text(), w.pages.ai._sum_lbl.text())

    # 2. 输入 + reset + 运行态
    w.pages.ai._symptom_input.setPlainText("动力不足，爬坡无力")
    w.pages.ai._notes_input.setPlainText("已换过空滤")
    sym, notes = w.pages.ai.get_input()
    ok("输入读取", sym == "动力不足，爬坡无力" and notes == "已换过空滤")
    w.pages.ai.reset()
    w.pages.ai.set_running(True)
    ok("运行态按钮禁用", not w.pages.ai._run_btn.isEnabled())
    ok("运行态文案", w.pages.ai._run_btn.text() == "诊断中…")

    # 3. 三阶段事件驱动（模拟 wizard 信号处理器）
    plan = CollectionPlan(
        streams=["发动机转速", "共轨压力", "车速"],
        working_conditions="原地挂空挡，怠速后急加速")
    w._on_ai_stage_done(1, "确认采集列表", plan)
    ok("阶段1 done + 采集计划卡可见", not w.pages.ai._plan_card_ref().isHidden()
       and w.pages.ai._plan_chips.count() >= 3)

    loc = Locatability(is_locatable=True, reason="转速与轨压数据完整，可原地定位")
    w._on_ai_stage_done(2, "是否需要路试", loc)
    ok("阶段2 done + 路试徽标", w.pages.ai._loc_verdict.text() == "可原地定位 · 无需路试")

    report_data = {
        "overallConclusion": "发动机的大脑（ECU）在报警，怀疑燃油计量单元的神经（线束）接触不良。",
        "diagnosisList": [{
            "faultPoint": "燃油计量单元(IMV)",
            "probability": "可能性最大",
            "simpleExplanation": "故障码 P2135 + 共轨压力波动，指向计量单元",
            "guideSteps": ["第一步，拔下 IMV 插头，<b>测量 1 号针脚</b>对地电压。<br>正常应为 5V。",
                           "第二步，测信号线与 ECU 侧 A23 针脚通断。"],
        }],
    }
    w._on_ai_stage_done(3, "输出维修报告", report_data)
    ok("阶段3 done + 报告卡可见", not w.pages.ai._report_card_ref().isHidden())
    ok("报告 HTML 渲染", "燃油计量单元" in w.pages.ai._report_browser.toHtml())

    w.pages.ai.set_running(False)
    ok("结束按钮恢复", w.pages.ai._run_btn.isEnabled()
       and w.pages.ai._run_btn.text() == "开始 AI 诊断")

    # 4. 错误路径
    w._on_ai_failed("未配置 DeepSeek API Key")
    ok("失败文案 + 按钮重试", "失败" in w.pages.ai._status_lbl.text()
       and w.pages.ai._run_btn.text() == "重试")

    # 5. load_from：模拟重跑后从 out_dir 恢复
    w.pages.ai.reset()
    (tmp / "ai_collection_plan.json").write_text(
        json.dumps({"streams": ["车速"], "working_conditions": "路试"}, ensure_ascii=False),
        encoding="utf-8")
    w.pages.ai.load_from(tmp)
    ok("load_from 恢复采集计划", not w.pages.ai._plan_card_ref().isHidden())

    # 6. set_report(None) → 按钮禁用
    w.pages.ai.set_report(None)
    ok("无报告按钮禁用", not w.pages.ai._run_btn.isEnabled())

    print(f"\n══ GUI PASS {PASS} / FAIL {FAIL} ══")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
