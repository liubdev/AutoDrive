#!/usr/bin/env python3
"""离屏渲染 AutoDrive 双视图 → PNG 预览（无需真机/DTS650）。

用途：调整样式后快速复查效果。输出（docs/design-v2/）：
  e-home.png      启动主页 · 设备选择（ct1：车型卡片）
  e-page2.png     分析页（ct2：面包屑 + 四节点步进器 + 输入条 + 真实结果全展开）
  e-real-window.png  分析页整窗（顶栏 + 面包屑 + 步进器 + 首屏内容）

报告数据为「真实结构」的示例（overallConclusion + diagnosisList 文本，
probability 为真实文字而非百分比），用于验证 widget 渲染。运行无需显示器。

用法: python scripts/render_preview.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QLabel

from ai.chain import CollectionPlan, Locatability
from ui.report import ReportLoader
from ui.wizard import MainWindow


def _flush(app, content):
    content.adjustSize()
    for _ in range(5):
        app.processEvents()


def main():
    app = QApplication([])
    w = MainWindow()
    w.resize(1000, 720)
    w.show()

    out_dir = ROOT / "docs" / "design-v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 主页：设备选择（ct1，默认选中轿车） ──
    _flush(app, w.home)
    w.grab().save(str(out_dir / "e-home.png"))

    # ── 进入分析页（ct2） ──
    w._on_device_selected("轿车")
    w.pages.ai._symptom_input.setText("动力不足，爬坡无力")

    # 构造 schema 准确的报告，展开②③节
    tmp = Path(tempfile.mkdtemp(prefix="e_render_"))
    (tmp / "fault_codes.txt").write_text(
        "P0100F9 空气流量计电路过高\nP208A13 柱塞泵驱动电路开路\n"
        "P009B13 轨压PCV驱动电路开路\nP2135 节气门位置传感器电压相关\n",
        encoding="utf-8")
    (tmp / "DataFlow_1.csv").write_text(
        "参数,值,单位,参考范围\n发动机转速,750,r/min,650-850\n共轨压力,320,bar,250-400\n",
        encoding="utf-8")
    w._out_dir = tmp
    rep = ReportLoader().load(tmp)
    w.pages.diag.set_report(rep)
    w.pages.diag._toggle_btn.click()          # 展开②采集明细
    app.processEvents()

    # 三段链路：采集计划 + 路试判断 + 维修报告（真实 diagnosisList 文本结构）
    w.pages.ai.show_plan(CollectionPlan(
        streams=["发动机转速", "共轨压力", "车速"],
        working_conditions="原地挂空挡，怠速后急加速").asdict())
    w.pages.ai.show_locatability(Locatability(
        is_locatable=True, reason="转速与轨压数据完整，可原地定位").asdict())
    report_data = {
        "overallConclusion":
            "四个故障码集中在进气计量与高压共轨执行器电路，同时出现且同属「电气开路/过高」类，"
            "指向线束供电 / 搭铁异常。",
        "diagnosisList": [
            {"faultPoint": "执行器共用地线回路接触不良",
             "probability": "可能性最大",
             "simpleExplanation": "HFM/PCV/柱塞泵共用搭铁点 G301，一处氧化即可同时拉高多路报警。",
             "guideSteps": ["第一步，点火 ON，万用表测 G301 电压降应 <0.1V。",
                            "第二步，摇动线束观察故障是否复现，确认插接件无氧化。"]},
            {"faultPoint": "主继电器供电分支 / 插接件氧化",
             "probability": "次高",
             "simpleExplanation": "供电支路保险接触不良或 X1 插接件进水，导致驱动电压跌落。",
             "guideSteps": ["点火 ON 测 PCV/柱塞泵供电端，标准约 12V；检查保险与 X1 端子。"]},
            {"faultPoint": "ECU 输出级故障",
             "probability": "较少",
             "simpleExplanation": "供电、搭铁均正常时考虑 ECU 内部驱动级损坏。",
             "guideSteps": ["示波器确认 PCV 驱动占空比；必要时更换 ECU 并刷新标定。"]},
        ],
    }
    w.pages.ai.show_report(report_data)
    w.pages.ai.set_stage(1, "done", "完成")
    w.pages.ai.set_stage(2, "done", "完成")
    w.pages.ai.set_stage(3, "done", "完成")
    w.pages.ai.set_summary("轿车", "动力不足，爬坡无力")
    w._set_phase("report")
    w.pages.ai.set_status("诊断完成 — 可查看采集计划 / 路试判断 / 维修报告")

    # 强制完成整棵布局（滚动区内容高度按 sizeHint 撑开）后再抓图
    content = w.pages.diag._scroll.widget()
    _flush(app, content)
    w.resize(1000, 720)
    app.processEvents()
    for _ in range(3):
        app.processEvents()
    pills = [l for l in w.pages.ai._report_card_ref().findChildren(QLabel)
             if l.objectName() == "CauseProb"]
    assert all(l.height() > 0 for l in pills), "概率标签布局未完成，抓图会缺失"

    # 分析页整窗（含顶栏/面包屑/步进器）：把滚动区拉高到能看到全部内容
    diag = w.pages.diag
    H = content.sizeHint().height() + 240   # + 面包屑/步进器/留白
    w.resize(1000, min(3000, H))
    _flush(app, content)
    diag.grab().save(str(out_dir / "e-page2.png"))
    w.resize(1000, 720)
    app.processEvents()
    w.grab().save(str(out_dir / "e-real-window.png"))
    print("saved docs/design-v2/e-home.png + e-page2.png + e-real-window.png")


if __name__ == "__main__":
    main()
