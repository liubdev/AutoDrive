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

from PySide6.QtWidgets import QScrollArea

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


def _chip_texts(layout):
    """收集 QHBoxLayout 内 Chip QLabel 文本"""
    out = []
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if w is not None and getattr(w, "text", None):
            out.append(w.text())
    return out


def _scroll_count(widget):
    """统计 widget 子树内的 QScrollArea 数量"""
    return len(widget.findChildren(QScrollArea))


def main():
    from PySide6.QtWidgets import QApplication, QLabel
    from ui.report import ReportLoader
    from ui.wizard import MainWindow
    from ui.pages import PhaseBar
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

    # 0. 双视图：启动即主页（设备选择），点击车型卡进入分析页
    from PySide6.QtWidgets import QStackedWidget
    ok("启动为双视图结构", isinstance(w._stack, QStackedWidget)
       and w._stack.currentIndex() == 0)
    ok("主页存在（设备选择）", hasattr(w, "home") and w.home._cards
       and len(w.home._cards) == 4)
    w._on_device_selected("轿车")
    ok("点车型卡 → 分析页", w._stack.currentIndex() == 1
       and w._vehicle == "轿车")
    ok("面包屑显示车型", w.pages.diag._crumb_lbl.text() == "轿车 诊断",
       w.pages.diag._crumb_lbl.text())
    ok("进入即步进器①✓②●", [d.property("stepState") for (d, _l, _s) in w._phase_bar._dots]
       == ["done", "current", "next", "next"])
    ok("摘要条显示车型", w.pages.ai._summary_lbl.text().startswith("车型：轿车"),
       w.pages.ai._summary_lbl.text())

    # 0b. 主页常见问题 + DTS 诊断仪运行
    ok("主页常见问题 2×3", len(w.home._faq_btns) == 6
       and all(b.objectName() == "FaqChip" for b in w.home._faq_btns))
    ok("DTS 诊断仪运行按钮就绪", hasattr(w.home, "_run_btn")
       and w.home._run_btn.text() == "运行" and w.home._run_btn.isEnabled())
    w._on_back()
    w.home._toggle_faq("动力不足")
    ok("常见问题点击选中", w.home.selected_faq() == "动力不足")
    w._on_home_run()
    ok("运行 → 分析页且预填症状", w._stack.currentIndex() == 1
       and w.pages.ai._symptom_input.text() == "动力不足",
       w.pages.ai._symptom_input.text())

    # 1. set_report → 按钮可用 + 数据计数
    w._out_dir = tmp
    report = ReportLoader().load(tmp)
    w.pages.ai.set_report(report)
    ok("报告加载后发送按钮可用", w.pages.ai._run_btn.isEnabled())
    ok("数据计数显示", "1 条故障码" in w.pages.ai._sum_lbl.text(), w.pages.ai._sum_lbl.text())

    # 2. 输入 + reset + 运行态
    w.pages.ai._symptom_input.setText("动力不足，爬坡无力")
    w.pages.ai._notes_input.setText("已换过空滤")
    sym, notes = w.pages.ai.get_input()
    ok("输入读取", sym == "动力不足，爬坡无力" and notes == "已换过空滤")
    w.pages.ai.reset()
    w.pages.ai.set_running(True)
    ok("运行态按钮禁用", not w.pages.ai._run_btn.isEnabled())
    ok("运行态文案", w.pages.ai._status_lbl.text() == "诊断中…",
       w.pages.ai._status_lbl.text())

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
    ok("报告 widget 渲染", "燃油计量单元" in w.pages.ai._report_texts())
    ok("报告后出现操作按钮", not w.pages.ai._action_card_ref().isHidden()
       and w.pages.ai._export_btn.text() == "导出诊断报告")
    w._on_ai_finished({"plan": None, "locatability": None,
                       "report": report_data, "out_dir": str(tmp)})
    ok("步进器 report 阶段", [d.property("stepState") for (d, _l, _s) in w._phase_bar._dots]
       == ["done", "done", "done", "current"])
    ok("结束按钮恢复", w.pages.ai._run_btn.isEnabled()
       and w.pages.ai._status_lbl.text() == "诊断完成 — 可查看采集计划 / 路试判断 / 维修报告",
       w.pages.ai._status_lbl.text())

    # 4. 错误路径
    w._on_ai_failed("未配置 DeepSeek API Key")
    ok("失败文案 + 可重试", "失败" in w.pages.ai._status_lbl.text()
       and w.pages.ai._run_btn.isEnabled(), w.pages.ai._status_lbl.text())

    # 5. load_from：模拟重跑后从 out_dir 恢复
    w.pages.ai.reset()
    (tmp / "ai_collection_plan.json").write_text(
        json.dumps({"streams": ["车速"], "working_conditions": "路试"}, ensure_ascii=False),
        encoding="utf-8")
    w.pages.ai.load_from(tmp)
    ok("load_from 恢复采集计划", not w.pages.ai._plan_card_ref().isHidden())

    # 6. set_report(None) → 回到等待态（发送按钮始终可用：发送即采集+AI）
    w.pages.ai.set_report(None)
    ok("无报告回到等待态", w.pages.ai._run_btn.isEnabled()
       and w.pages.ai._sum_lbl.text() == "等待运行数据",
       w.pages.ai._sum_lbl.text())

    # 6b. 面包屑返回主页（未运行时）
    w._on_back()
    ok("返回主页", w._stack.currentIndex() == 0)
    w._on_device_selected("SUV")
    ok("再次进入分析页（SUV）", w._stack.currentIndex() == 1
       and w.pages.diag._crumb_lbl.text() == "SUV 诊断")

    # 7. 单页连续流：节可见性 / 摘要 chips / 展开收起
    diag = w.pages.diag
    ok("单页初始②③节隐藏", diag._data_section.isHidden() and diag.ai.isHidden())
    diag.set_report(report)
    ok("set_report 后②③节可见", not diag._data_section.isHidden()
       and not diag.ai.isHidden())
    chips = _chip_texts(diag._sum_chips)
    ok("摘要 chips 含计数", "1 条故障码" in chips and "2 项数据流" in chips, chips)

    diag.data.setVisible(False)          # 保证起点是收起态
    diag._toggle_btn.click()
    ok("展开明细后 detail 可见", not diag.data.isHidden())
    diag._toggle_btn.click()
    ok("收起明细后 detail 隐藏", diag.data.isHidden())
    ok("展开按钮文案复位", diag._toggle_btn.text() == "▸ 展开明细")

    # 8. PhaseBar 四节点（ct2，纯展示，不可点击）
    pb = PhaseBar()
    pb.set_phase("run")
    st = [d.property("stepState") for (d, _l, _s) in pb._dots]
    ok("PhaseBar run 阶段", st == ["done", "current", "next", "next"], st)
    pb.set_phase("data")
    st = [d.property("stepState") for (d, _l, _s) in pb._dots]
    ok("PhaseBar data 阶段", st == ["done", "done", "current", "next"], st)
    pb.set_phase("ai")
    st = [d.property("stepState") for (d, _l, _s) in pb._dots]
    ok("PhaseBar ai 阶段", st == ["done", "done", "current", "next"], st)
    pb.set_phase("report")
    st = [d.property("stepState") for (d, _l, _s) in pb._dots]
    ok("PhaseBar report 阶段", st == ["done", "done", "done", "current"], st)

    # 9. embed 模式：无内滚 / 无空态 / 无页面级返回按钮
    ok("RunPage embed 无内滚", _scroll_count(diag.run) == 0)
    ok("DataPage embed 无内滚", _scroll_count(diag.data) == 0)
    ok("AiPage embed 无内滚", _scroll_count(diag.ai) == 0)
    ok("DataPage embed 无空态", not hasattr(diag.data, "_empty"))
    ok("RunPage embed 无底部返回", diag.run._back_btn is None)

    # 10. DataPage 重复 set_report 不叠加渲染
    n = diag.data._stack_layout.count()
    diag.data.set_report(report)
    ok("重复 set_report 不叠加", diag.data._stack_layout.count() == n,
       f"{n} -> {diag.data._stack_layout.count()}")

    # 11. reset_all 收起②③、复位展开按钮
    diag.reset_all()
    ok("reset_all 收起②③", diag._data_section.isHidden() and diag.ai.isHidden()
       and diag._toggle_btn.text() == "▸ 展开明细")

    # 12. 采集完成 → 自动触发 AI（未配置 key 时软跳过，不打断收尾）
    import ai.deepseek as _ds
    w._out_dir = tmp
    w._on_flow_done(None)               # 有故障码 → pending 置位、PhaseBar→③AI分析中
    ok("流程完成 pending 自动 AI", w._pending_auto_ai is True
       and w._phase_bar._dots[2][0].property("stepState") == "current")
    _saved_cfg = _ds.DeepSeekClient.configured
    _ds.DeepSeekClient.configured = property(lambda self: False)
    try:
        w._on_run_finished()
    finally:
        _ds.DeepSeekClient.configured = _saved_cfg
    ok("未配置 key 软跳过自动 AI", w._ai_running is False
       and "跳过" in w.pages.ai._status_lbl.text(), w.pages.ai._status_lbl.text())
    ok("软跳过后复位就绪", w._pending_auto_ai is False
       and w._dev_status.text() == "○ 就绪")

    print(f"\n══ GUI PASS {PASS} / FAIL {FAIL} ══")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
