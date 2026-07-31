"""
DTS 自动控制 - 完整数据流保存流程
"""

import sys, logging, warnings, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
log = logging.getLogger("run_dts")

from automation.apps.dts import DtsApp


def step(n, name, ok):
    log.info(f"  {'✓' if ok else '✗'} [{n}] {name}")


def make_output_dir():
    """创建带时间戳的输出目录，返回目录路径"""
    from datetime import datetime
    root = Path(__file__).resolve().parent.parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = root / "data" / "reports" / f"DTS_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main():
    log.info("=" * 40)
    log.info("  DTS 自动控制")
    log.info("=" * 40)

    # 创建本次执行的输出目录
    out_dir = make_output_dir()
    log.info(f"  输出目录: {out_dir}")

    app = DtsApp()

    # ── 第1步: 启动 ──
    ok = app.ensure_running(timeout=30)
    step(1, "启动 DTS", ok)
    if not ok:
        return

    # ── 第2步: 确认 ──
    ok = app.confirm(timeout=15)
    step(2, "确认弹窗", ok)

    # ── 第3步: 一键进入 ──
    ok = app.one_click_enter(timeout=15)
    step(3, "一键进入", ok)

    time.sleep(5)

    # ── 第4步: 点击进入系统 ──
    ok = app.enter_system(timeout=15)
    step(4, "进入系统", ok)

    time.sleep(12)

    # ── 第5步: 发动机系统诊断 ──
    ok = app.send_enter(timeout=15)
    step(5, "诊断", ok)

    time.sleep(12)

    # ── 第6步: 空格确认 ──
    ok = app.send_space(timeout=15)
    step(6, "空格确认", ok)

    time.sleep(12)

    # ── 第7步: 回车2.0 ──
    ok = app.send_enter(timeout=15)
    step(7, "发动机2.0", ok)

    # ── 第8步: 空格 + 保存 ──
    ok = app.send_space(timeout=15)
    step(8, "空格确认", ok)

    # 保存版本信息
    # 保存版本信息
    version_path = out_dir / "version_info.txt"
    text = app._read_edit_text()
    if text:
        with open(version_path, "w", encoding="utf-8") as f:
            f.write(text)
        log.info(f"  ✓ 版本信息已保存: {version_path}")
    else:
        log.info("  ✗ 版本信息保存失败")

    ok = app.send_space(timeout=15)
    step(8, "空格确认", ok)

    # 进入故障码选项
    app.send_keys("{ENTER}")
    # ── 获取故障码 ──
    data = app.copy_all_rows(copy_btn_id="1011")
    if data:
        fault_path = out_dir / "fault_codes.txt"
        with open(fault_path, "w", encoding="utf-8") as f:
            f.write("\n".join(data))
        log.info(f"  ✓ 故障码已保存: {fault_path}")

    # ── 返回导航到数据流 ──
    back_btn = app.window.child_window(
        auto_id="2", control_type="Button", found_index=0
    )
    if back_btn.exists(timeout=3):
        log.info("点击 返回 按钮")
        back_btn.click_input()

    # ── 导航到数据流 ──
    app.send_keys("{DOWN 2}{ENTER}")
    time.sleep(2)
    app.send_keys("{DOWN 6}{ENTER}")
    time.sleep(2)
    app.send_keys("{ENTER}")
    time.sleep(2)

    # ── 翻页 + 全选 ──
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

    # ── 保存列表 ──
    import pywinauto.keyboard as kb

    save_btn = app.window.child_window(
        auto_id="1013", control_type="Button", found_index=0
    )
    log.info("点击 保存列表 按钮")
    save_btn.click_input()
    time.sleep(0.5)
    kb.send_keys("DataFlow_List_All.txt{ENTER}")

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

    # ── 载入列表 ──
    load_btn = app.window.child_window(
        auto_id="1118", control_type="Button", found_index=0
    )
    log.info("点击 载入列表 按钮")
    load_btn.click_input()
    kb.send_keys("DataFlow_List_All.txt{ENTER}{ENTER}{ENTER}")
    time.sleep(10)

    # ── 返回 + 确认 ──
    back_btn = app.window.child_window(
        auto_id="1042", control_type="Button", found_index=0
    )
    if back_btn.exists(timeout=3):
        log.info("点击 返回 按钮")
        back_btn.click_input()
    time.sleep(12)

    exit_btn = app.window.child_window(
        auto_id="1", control_type="Button", found_index=0
    )
    if exit_btn.exists(timeout=3):
        exit_btn.click_input()

    # ── 读取保存路径 ──
    time.sleep(1)
    csv = app.extract_csv_path()
    log.info(f"  CSV: {csv}" if csv else "  CSV: 未找到")

    app.disconnect()
    log.info("[完成]")


main()
