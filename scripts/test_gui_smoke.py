#!/usr/bin/env python3
"""GUI 冒烟：offscreen 实例化 MainWindow，走一遍 LCS700 新 UI 导航 / 主题 / 演示降级 / 真实链路接线。

用法: python scripts/test_gui_smoke.py
目标断言 ≥ 55。
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 管道输出时 stdout 编码在启动时已定（Windows 默认 cp1252），此处强制 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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


def _frames(page, prop=None, oname=None):
    """按动态属性 card / objectName 收集页面内 QFrame。"""
    from PySide6.QtWidgets import QFrame

    out = []
    for f in page.findChildren(QFrame):
        if prop and f.property("card") != prop:
            continue
        if oname and f.objectName() != oname:
            continue
        out.append(f)
    return out


def main():
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QLineEdit,
        QPushButton,
        QStackedWidget,
    )

    # 干净起始：清掉旧设备/主题残留，保证 d0/d1/d2 全在
    QSettings("AutoDrive", "AutoDrive").clear()

    from ui.report import ReportLoader, ReportStore
    from ui.wizard import MainWindow
    from ui.widgets import PhaseBar
    from ui.appshell import PAGE_ORDER, PAGE_SPECS

    # 夹具 out_dir
    tmp = Path(tempfile.mkdtemp(prefix="ai_gui_"))
    (tmp / "fault_codes.txt").write_text(
        "P2135 节气门位置传感器电压相关性故障\n", encoding="utf-8"
    )
    (tmp / "DataFlow_List_1.txt").write_text(
        "发动机转速\n共轨压力\n车速\n", encoding="utf-8"
    )

    app = QApplication([])
    w = MainWindow()
    w.show()
    QTest.qWait(30)

    home = w.home
    ai = w.ai_diag

    # ── 1. 主题（深色默认 + 浅色切换持久化） ──
    ok(
        "主题默认深色",
        w.theme.resolved == "dark" and w.home.property("ui/mode") == "dark",
    )
    w.theme.set_theme("light")
    QTest.qWait(10)
    ok(
        "切浅色 → resolved light + 属性同步",
        w.theme.resolved == "light" and w.home.property("ui/mode") == "light",
    )
    w.theme.set_theme("dark")
    QTest.qWait(10)
    ok("还原深色", w.theme.resolved == "dark" and w.home.property("ui/mode") == "dark")

    # ── 2. 外壳与主页结构 ──
    ok("启动即主页", w.shell.current_page() == "home")
    ok("双视图结构（QStackedWidget）", isinstance(w._stack, QStackedWidget))
    ok(
        "核心 3 页预构建（其余懒加载）",
        len(w.pages) == 3 and set(w.pages) == {"home", "ai-diagn", "settings"},
        f"pages={sorted(w.pages)}",
    )
    ok(
        "设备卡 3 台 + 1 添加",
        len(home._dev_cards) == 3
        and len(
            [f for f in home.findChildren(QFrame) if f.property("card") == "dev-add"]
        )
        == 1,
    )
    ok(
        "设备卡计数含添加卡",
        len([f for f in home.findChildren(QFrame) if f.property("card") == "dev-add"])
        == 1,
    )
    ok(
        "AI 输入条存在",
        isinstance(home._ai_text, QLineEdit) and home._ai_text.objectName() == "aiText",
    )
    ok("发送按钮存在", hasattr(home, "_send_btn"))
    ok("常见故障类别 8 个", len(home._symp_cat_btns) == 8)
    ok("常见故障项按钮 ≥ 2", len(home._symp_item_btns) >= 2)

    # ── 3. 主页交互 ──
    home.select_device("d0")
    ok("选择设备 d0", home.selected_device_id() == "d0")
    ok("selected_device 返回 dict", (home.selected_device() or {}).get("id") == "d0")
    home._toggle_item("动力不足")
    ok("选中故障现象", "动力不足" in home.selected_symptoms())
    home._ai_text.setText("发动机亮故障灯")
    ok("问题文本读取", home.question_text() == "发动机亮故障灯")
    ok("has_input True（文本）", home.has_input())
    home._ai_text.clear()
    ok("has_input True（仅症状）", home.has_input())
    home._toggle_item("动力不足")
    ok("再点取消选择", "动力不足" not in home.selected_symptoms())

    # ── 4. _on_start_ai 校验与分派 ──
    home.select_device(None)
    w._on_start_ai()
    ok("未选设备 → 留在主页", w.shell.current_page() == "home" and not w._ai_running)
    home.select_device("d0")
    w._on_start_ai()  # 无输入 → 校验拦截
    ok("无输入 → 拦截且不运行", w.shell.current_page() == "home" and not w._ai_running)
    home._toggle_item("动力不足")

    dts_called = []
    w._start_dts_collection = lambda: dts_called.append(1)  # 打桩：不真启线程
    w._on_start_ai()
    ok(
        "DTS 设备 → 走真实采集",
        dts_called == [1] and w.shell.current_page() == "ai-diagn",
        dts_called,
    )
    ok(
        "面包屑 = 设备 诊断",
        ai._crumb_text.text() == "您的设备1：DTS 诊断",
        ai._crumb_text.text(),
    )

    # ── 5. 演示降级：X5 未接入自动化 → 演示数据 ──
    w._start_dts_collection = None
    w._on_restart()  # 回主页
    ok(
        "重新诊断 → 回主页",
        w.shell.current_page() == "home" and ai._result_tag.isHidden(),
    )
    home.select_device("d1")
    w._on_start_ai()  # 症状「动力不足」仍选中
    ok(
        "X5 → 进入 ai-diagn 演示降级",
        w.shell.current_page() == "ai-diagn" and w._ai_running,
    )
    QTest.qWait(3600)  # DYN_MSGS 6 条 × 450ms + 收尾
    ok("报告卡可见", ai._result_card.isVisible() and not ai._result_tag.isHidden())
    texts = ai._report_texts()
    ok("报告含「氧传感器」", "氧传感器" in texts)
    ok("原因条渲染", "催化转化器" in texts and "油箱盖" in texts, texts)
    ok("动态信息 6 条", ai._dyn_list.count() == 6, ai._dyn_list.count())
    ok("车辆信息故障码 3 条", ai._veh_dtc_list.count() == 3, ai._veh_dtc_list.count())
    ok(
        "VIN 填充",
        ai._veh_vals["vin"].text() == "LSVAM4187C2123456",
        ai._veh_vals["vin"].text(),
    )
    ok("排查步骤 5 步", len(ai._steps) == 5, len(ai._steps))
    ok("步骤翻页器 1 / 5", ai._step_pager.text() == "1 / 5", ai._step_pager.text())
    ok(
        "步进器 report 阶段",
        ai._steps_bar._dots[3][0].property("stepState") == "current",
    )
    ok("完成 → 状态就绪", w._dev_status.text() == "○ 就绪" and not w._ai_running)
    ok(
        "完成 → 按钮恢复可用",
        ai._export_btn.isEnabled() and ai._restart_btn.isEnabled(),
    )

    # ── 6. 导出 AI 报告（写夹具目录，不污染 reports_dir） ──
    from ui.lcsdata import DEMO_AI_REPORT

    w._out_dir = tmp
    w._export_ai_report(DEMO_AI_REPORT)
    md = tmp / "ai_report.md"
    ok(
        "导出 Markdown 成功",
        md.exists() and "氧传感器" in md.read_text(encoding="utf-8"),
    )

    # ── 7. 全页导航 + 底栏按钮与 PAGE_SPECS 一致 ──
    nav_bad = []
    for pid in PAGE_ORDER:
        w.shell.goPage(pid)
        app.processEvents()
        if w.shell.current_page() != pid:
            nav_bad.append(pid)
    ok("遍历 19 页 goPage 无异常", not nav_bad, nav_bad)
    ok(
        "懒加载全部建成 19 页",
        len(w.pages) == 19 and w.shell.stack.count() == 19,
        f"pages={len(w.pages)} stack={w.shell.stack.count()}",
    )
    bb_bad = []
    for pid in PAGE_ORDER:
        w.shell.goPage(pid)
        bb = [b for b in w.shell.findChildren(QPushButton) if b.objectName() == "bbBtn"]
        if len(bb) != len(PAGE_SPECS[pid].btns):
            bb_bad.append((pid, len(bb), len(PAGE_SPECS[pid].btns)))
    ok("每页底栏按钮数与 PAGE_SPECS 一致", not bb_bad, bb_bad)

    # ── 8. 骨架占位页计数 ──
    w.shell.goPage("special")
    ok("专用诊断仪 grid5 == 10", len(_frames(w.pages["special"], prop="grid5")) == 10)
    w.shell.goPage("advanced")
    ok("高级功能 grid4 == 4", len(_frames(w.pages["advanced"], prop="grid4")) == 4)
    w.shell.goPage("ebs-dtc")
    ok("EBS 故障码行 == 10", len(_frames(w.pages["ebs-dtc"], oname="ecRow")) == 10)
    w.shell.goPage("can")
    ok("CAN 扫描行 == 6", len(_frames(w.pages["can"], oname="listRow")) == 6)
    w.shell.goPage("ebs")
    ok("EBS 电控系统行 == 7", len(_frames(w.pages["ebs"], oname="listRow")) == 7)

    # ── 9. 报告页：真实 ReportStore 扫描 / 演示种子回退 ──
    store = ReportStore()
    metas = store.list_reports()
    ok("ReportStore 扫描返回列表", isinstance(metas, list))
    w.shell.goPage("report")
    tag = w.pages["report"]._count_tag.text()
    ok("报告计数标签", bool(tag) and "份报告" in tag, tag)
    ok(
        "报告列表有行（真实或演示）",
        w.pages["report"]._list.count() >= 2,
        w.pages["report"]._list.count(),
    )

    # ── 10. 设置页主题 seg 高亮 + 信号接线 ──
    w.shell.goPage("settings")
    sett = w.pages["settings"]
    ok("设置项 11 条", len(_frames(sett, prop="set-row")) == 11)
    sett.set_current_theme("light")
    seg = dict(sett._theme_btns)
    ok(
        "切浅色 → seg 高亮同步",
        seg["light"].property("sel") == "on" and seg["dark"].property("sel") == "off",
    )
    sett._pick_theme("dark")  # 走真实信号 → wizard → ThemeManager
    QTest.qWait(10)
    ok("主题信号接线生效", w.theme.resolved == "dark")

    # ── 11. PhaseBar 四阶段（独立控件） ──
    pb = PhaseBar()
    pb.set_phase("run")
    ok(
        "PhaseBar run",
        [d.property("stepState") for (d, _l, _s) in pb._dots]
        == ["done", "current", "next", "next"],
    )
    pb.set_phase("data")
    ok(
        "PhaseBar data",
        [d.property("stepState") for (d, _l, _s) in pb._dots]
        == ["done", "done", "current", "next"],
    )
    pb.set_phase("ai")
    ok(
        "PhaseBar ai",
        [d.property("stepState") for (d, _l, _s) in pb._dots]
        == ["done", "done", "current", "next"],
    )
    pb.set_phase("report")
    ok(
        "PhaseBar report",
        [d.property("stepState") for (d, _l, _s) in pb._dots]
        == ["done", "done", "done", "current"],
    )

    # ── 12. 采集完成 → 自动 AI（未配置 key 软跳过，不打断收尾） ──
    import ai.deepseek as _ds

    w._out_dir = tmp
    w._on_flow_done(None)
    ok(
        "流程完成 pending 自动 AI",
        w._pending_auto_ai is True
        and w.ai_diag._steps_bar._dots[2][0].property("stepState") == "current",
    )
    _saved_cfg = _ds.DeepSeekClient.configured
    _ds.DeepSeekClient.configured = property(lambda self: False)
    try:
        w._on_run_finished()
    finally:
        _ds.DeepSeekClient.configured = _saved_cfg
    ok(
        "未配置 key 软跳过自动 AI",
        w._ai_running is False and "跳过" in ai._status_lbl.text(),
        ai._status_lbl.text(),
    )
    ok(
        "软跳过后复位就绪",
        w._pending_auto_ai is False and w._dev_status.text() == "○ 就绪",
    )

    # ── 13. ReportLoader 真实夹具解析（版本 / 故障码 / 数据流） ──
    report = ReportLoader().load(tmp)
    ok("夹具故障码解析", len(report.faults) == 1 and report.faults[0].code == "P2135")
    ok("夹具数据流解析", len(report.flows) >= 3, len(report.flows))
    ok("has_data 判定", report.has_data is True)

    print(f"\n══ GUI PASS {PASS} / FAIL {FAIL} ══")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
