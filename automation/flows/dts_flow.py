"""
DTS 数据流保存流程 — 配置化定义

把原来的线性脚本 scripts/run_dts.py 移植为 FlowStep 列表：
  每个步骤 = 动作(action) + 验证(wait_for_control) + 重试

GUI (autogui.py) 与控制台 (scripts/run_dts.py) 共用同一份流程定义。
"""

import time
import logging
from pathlib import Path
from datetime import datetime

import pywinauto.keyboard as kb

from automation.apps.dts import DtsApp
from automation.flow.engine import FlowStep

log = logging.getLogger("autodrive.flow.dts")


def make_output_dir(root: Path = None) -> Path:
    """创建带时间戳的输出目录 data/reports/DTS_YYYYMMDD_HHMMSS/"""
    root = root or Path(__file__).resolve().parent.parent.parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = root / "data" / "reports" / f"DTS_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def build_dts_flow(app: DtsApp, out_dir: Path, max_flows: int = 5) -> list:
    """
    构建 DTS 完整流程的步骤列表

    Args:
        app: DtsApp 实例（已连接或可启动）
        out_dir: 输出目录（存放 version_info.txt / fault_codes.txt / 数据流列表）
        max_flows: 最多处理的数据流个数（防止死循环）

    Returns:
        list[FlowStep]
    """
    steps = []

    # ── 第1步: 启动 ──
    steps.append(FlowStep("启动 DTS",
                          action=lambda: app.ensure_running(timeout=12)))

    # ── 第2步: 确认 ──
    steps.append(FlowStep("确认",
                          action=lambda: app.confirm(timeout=15),
                          verify={"auto_id": "1197"}, timeout=20,
                          continue_on_missing=True))

    # ── 第3步: 一键进入 ──
    steps.append(FlowStep("一键进入",
                          action=lambda: app.one_click_enter(),
                          verify={"auto_id": "6"}, timeout=20,
                          continue_on_missing=True))

    # ── 第4步: 点击进入系统 ──
    steps.append(FlowStep("点击进入系统",
                          action=lambda: app.enter_system(),
                          verify={"auto_id": "1046"}, timeout=20,
                          continue_on_missing=True))

    # ── 第5步: 发动机系统诊断 ──
    steps.append(FlowStep("发动机系统诊断",
                          action=lambda: app.send_enter(),
                          verify={"auto_id": "1058"}, timeout=20,
                          continue_on_missing=True))

    # ── 第6步: 直接进入 ──
    steps.append(FlowStep("直接进入",
                          action=lambda: app.send_space(),
                          verify={"auto_id": "1046"}, timeout=20,
                          continue_on_missing=True))

    # ── 第7步: 发动机2.0T ──
    steps.append(FlowStep("发动机2.0T",
                          action=lambda: app.send_enter(),
                          verify={"auto_id": "1058"}, timeout=20,
                          continue_on_missing=True))

    # ── 第8步: 空格 + 版本信息 ──
    steps.append(FlowStep("空格确认",
                          action=lambda: app.send_space(timeout=15),
                          verify={"auto_id": "1202", "control_type": "Edit"},
                          timeout=20,
                          continue_on_missing=True))

    # ── 第9步: 保存版本信息 ──
    steps.append(FlowStep("保存版本信息",
                          action=_make_save_version(app, out_dir)))

    # ── 第10步: 空格确认 ──
    steps.append(FlowStep("空格确认",
                          action=lambda: app.send_space(timeout=15)))

    # ── 第11步: 进入故障码选项 ──
    steps.append(FlowStep("进入故障码选项",
                          action=lambda: bool(app.send_keys("{ENTER}"))))

    # ── 第12步: 获取故障码 ──
    steps.append(FlowStep("获取故障码",
                          action=_make_copy_fault_codes(app, out_dir),
                          timeout=180))

    # ── 第13步: 返回 ──
    steps.append(FlowStep("返回",
                          action=_make_go_back(app)))

    # ── 第14步: 导航到数据流菜单 ──
    steps.append(FlowStep("导航到数据流菜单",
                          action=_make_nav_data_flow(app)))

    # ── 第15步: 循环读取数据流 ──
    steps.append(FlowStep("循环读取数据流",
                          action=_make_data_flow_loop(app, out_dir, max_flows),
                          timeout=1200))

    return steps


# ═══════════════════════════════════════════════════════════
#  步骤动作（闭包工厂）
# ═══════════════════════════════════════════════════════════

def _make_save_version(app: DtsApp, out_dir: Path):
    def action():
        text = app._read_edit_text()
        if text:
            version_path = out_dir / "version_info.txt"
            with open(version_path, "w", encoding="utf-8") as f:
                f.write(text)
            log.info(f"✓ 版本信息已保存: {version_path}")
            return True
        log.warning("版本信息保存失败")
        return False
    return action


def _make_copy_fault_codes(app: DtsApp, out_dir: Path):
    def action():
        data = app.copy_all_rows(copy_btn_id="1011")
        if data:
            fault_path = out_dir / "fault_codes.txt"
            with open(fault_path, "w", encoding="utf-8") as f:
                f.write("\n".join(data))
            log.info(f"✓ 故障码已保存: {fault_path}")
        else:
            log.warning("未获取到故障码")
        return True
    return action


def _make_go_back(app: DtsApp):
    def action():
        back_btn = app.window.child_window(
            auto_id="2", control_type="Button", found_index=0
        )
        if back_btn.exists(timeout=3):
            back_btn.click_input()
            return True
        log.warning("返回按钮(auto_id=2)不存在")
        return False
    return action


def _make_nav_data_flow(app: DtsApp):
    def action():
        app.send_keys("{DOWN 2}{ENTER}")
        time.sleep(0.2)
        app.send_keys("{DOWN 6}{ENTER}")
        time.sleep(0.2)
        app.send_keys("{ENTER}")
        return True
    return action


def _make_data_flow_loop(app: DtsApp, out_dir: Path, max_flows: int):
    def action():
        return _data_flow_loop(app, out_dir, max_flows)
    return action


def _data_flow_loop(app: DtsApp, out_dir: Path, max_flows: int) -> bool:
    """
    循环处理多个数据流（数量不确定）

    进入每个数据流 → 取第一项 → 与上一个对比（相同则停止）
    → 保存列表 → 载入列表 → 返回 → 下一个
    """
    prev_item = None
    flow_count = 0

    while flow_count < max_flows:
        first_item = app.get_first_list_item()
        flow_count += 1
        log.info(f"  —— 数据流{flow_count} 第一项: {first_item} ——")

        # 与上一个数据流相同 → 已是最后一个
        if prev_item is not None and first_item and first_item == prev_item:
            log.info(f"  数据流{flow_count}与上一个相同，停止")
            break
        prev_item = first_item

        # 执行当前数据流操作
        _process_flow(app, flow_count)
        log.info(f"  数据流{flow_count} 完成")
        app.wait_for_control("1")
        # 弹窗确定
        exit_btn = app.window.child_window(
            auto_id="1", control_type="Button", found_index=0
        )
        if exit_btn.exists(timeout=3):
            exit_btn.click_input()

        # ── 读取保存路径 ──
        app.wait_for_control("1058")
        csv = app.extract_csv_path()
        exit_btn = app.window.child_window(
            auto_id="1058", control_type="Button", found_index=0
        )
        if exit_btn.exists(timeout=3):
            log.info("点击 csv 路径界面 确认 按钮")
            exit_btn.click_input()

        log.info(f"  CSV: {csv}" if csv else "  CSV: 未找到")

        # 返回到读取所有数据流
        back = app.window.child_window(
            auto_id="2", control_type="Button", found_index=0
        )
        log.info("返回到读取所有数据流")
        back.click_input()
        # 返回主页
        app.wait_for_control("1129")

        # 切换到下一个数据流: DOWN + ENTER
        log.info("切换到下一个数据流...")
        app.send_keys("{DOWN}")
        time.sleep(0.2)
        app.send_keys("{ENTER}")
        # 确定
        app.wait_for_control("1028")

    log.info(f"共处理 {flow_count} 个数据流")
    return True


def _process_flow(app: DtsApp, flow_no: int):
    """执行单个数据流的操作: 翻页+全选+保存列表+载入列表"""
    # 每个数据流用独立的文件名
    file_name = f"DataFlow_List_{flow_no}.txt"
    log.info(f"  —— 数据流{flow_no} 使用文件: {file_name} ——")

    # 翻页 + 全选
    right_btn = app.window.child_window(
        auto_id="DownButton", control_type="Button", found_index=0
    )
    if right_btn.exists(timeout=3):
        for _ in range(12):
            for aid in ["1070", "1073"]:
                cb = app.window.child_window(
                    auto_id=aid, control_type="CheckBox", found_index=0
                )
                if cb.exists(timeout=0.5) and cb.get_toggle_state() == 0:
                    cb.click_input()
            right_btn.click_input()
            time.sleep(0.5)

    # 保存列表
    save_btn = app.window.child_window(
        auto_id="1013", control_type="Button", found_index=0
    )
    log.info("点击 保存列表 按钮")
    save_btn.click_input()
    time.sleep(0.5)
    kb.send_keys(f"{file_name}{{ENTER}}")

    # 处理覆盖弹窗
    for _ in range(8):
        btn = app.window.child_window(
            title="是(Y)", control_type="Button", found_index=0
        )
        if btn.exists(timeout=0.5):
            btn.click_input()
            break
        time.sleep(0.3)
    time.sleep(2)
    kb.send_keys("{ENTER}{ENTER}")

    # 载入列表
    load_btn = app.window.child_window(
        auto_id="1118", control_type="Button", found_index=0
    )
    log.info("点击 载入列表 按钮")
    load_btn.click_input()
    kb.send_keys(f"{file_name}{{ENTER}}{{ENTER}}{{ENTER}}")
    time.sleep(10)

    # 返回
    back_btn = app.window.child_window(
        auto_id="1042", control_type="Button", found_index=0
    )
    if back_btn.exists(timeout=3):
        log.info("点击 返回 按钮")
        back_btn.click_input()
    # 自定义文件名
    kb.send_keys(f"{file_name}")
