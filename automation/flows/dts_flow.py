"""
DTS 数据流保存流程 — 配置化定义

把原来的线性脚本 scripts/run_dts.py 移植为 FlowStep 列表：
  每个步骤 = 动作(action) + 验证(wait_for_control) + 重试

GUI (autogui.py) 与控制台 (scripts/run_dts.py) 共用同一份流程定义。
"""

import shutil
import time
import logging
from pathlib import Path
from datetime import datetime

from automation.apps.dts import DtsApp
from automation.flow.engine import FlowStep
from config import settings

log = logging.getLogger("autodrive.flow.dts")

# 当前运行的日志 handler（挂根 logger，输出到报告目录内同名 .log）。
# 同进程多次采集时先摘掉上一个再挂新的，避免 handler 累积、旧报告被续写。
_RUN_LOG_HANDLER = None


def close_run_log():
    """收口当前运行的报告同名日志（摘掉 handler 并关闭文件）。

    报告的完整生命周期（采集 + AI 诊断）结束后调用，避免后续无关日志
    （页面导航等）继续写进上一次报告的 .log。无活动运行日志时是安全空操作。
    """
    global _RUN_LOG_HANDLER
    root = logging.getLogger()
    if _RUN_LOG_HANDLER is not None:
        root.removeHandler(_RUN_LOG_HANDLER)
        try:
            _RUN_LOG_HANDLER.close()
        except Exception:  # noqa: BLE001
            pass
        _RUN_LOG_HANDLER = None


def _attach_run_log(out_dir: Path):
    """把本次运行的日志也写入 out_dir/DTS_xxx.log —— 与报告目录同名。

    报告目录自带执行日志：拷走报告文件夹即带走本次执行的完整日志
    （采集 + AI 诊断全程，root logger 上 autodrive.* / autocar.* 都落这里）。
    每日日志 data/logs/autodrive_YYYYMMDD.log 保留为会话级日志。
    下次采集（make_output_dir）会先摘掉上一个 handler，旧报告日志不再续写。
    """
    close_run_log()
    if out_dir is None:
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                            datefmt="%H:%M:%S")
    fh = logging.FileHandler(out_dir / f"{out_dir.name}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    root = logging.getLogger()
    root.addHandler(fh)
    global _RUN_LOG_HANDLER
    _RUN_LOG_HANDLER = fh


def make_output_dir(root: Path = None) -> Path:
    """创建带时间戳的输出目录 data/reports/DTS_YYYYMMDD_HHMMSS/

    同时把本次运行的日志挂到该目录内同名 .log（与报告名字保持一致）。
    """
    root = root or Path(__file__).resolve().parent.parent.parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = root / "data" / "reports" / f"DTS_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _attach_run_log(out_dir)
    return out_dir


def _desktop_dir() -> Path:
    """鲁棒解析用户桌面路径（DTS 保存数据流列表的默认目录，支持 OneDrive 重定向）"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0:
            p = Path(buf.value)
            if p.exists():
                return p
    except Exception:  # noqa: BLE001
        pass
    return Path.home() / "Desktop"


def _copy_dataflow_list(out_dir: Path, flow_no: int, desktop: Path = None) -> None:
    """DTS 把 DataFlow_List_N.txt 默认存到桌面 → 拷回 out_dir（AI 支持清单/数据流数据源）。

    desktop 参数供单测注入临时目录；默认真实桌面。
    """
    fname = f"DataFlow_List_{flow_no}.txt"
    src = (desktop if desktop is not None else _desktop_dir()) / fname
    try:
        if src.exists():
            shutil.copy2(src, out_dir / fname)
            log.info("  ✓ 数据流列表已拷入: %s", out_dir / fname)
        else:
            log.warning("  桌面未找到 %s（DTS 保存目录可能不是桌面）", src)
    except Exception as e:  # noqa: BLE001
        log.warning("  复制数据流列表失败: %s", e)


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
                          action=lambda: app.ensure_running(timeout=30)))

    # ── 第2步: 确认 ──
    steps.append(FlowStep("确认",
                          action=lambda: app.confirm(timeout=15),
                          verify={"auto_id": "1197"}, timeout=20,
                          continue_on_missing=True))

    # ── 第3步: 一键进入 ──
    steps.append(FlowStep("一键进入",
                          action=lambda: app.one_click_enter(),
                          verify={"auto_id": "6"}, timeout=20,
                          continue_on_missing=False))

    # ── 第4步: 点击进入系统 ──
    steps.append(FlowStep("点击进入系统",
                          action=lambda: app.enter_system(),
                          verify={"auto_id": "1046"}, timeout=20,
                          continue_on_missing=False))

    # ── 第5步: 发动机系统诊断 ──
    steps.append(FlowStep("发动机系统诊断",
                          action=lambda: app.send_enter(),
                          verify={"auto_id": "1058"}, timeout=20,
                          continue_on_missing=False))

    # ── 第6步: 直接进入 ──
    steps.append(FlowStep("直接进入",
                          action=lambda: app.send_space(),
                          verify={"auto_id": "1046"}, timeout=20,
                          continue_on_missing=False))

    # ── 第7步: 发动机2.0T ──
    steps.append(FlowStep("发动机2.0T",
                          action=lambda: app.send_enter(),
                          verify={"auto_id": "1058"}, timeout=20,
                          continue_on_missing=False))

    # ── 第8步: 空格 + 版本信息 ──
    steps.append(FlowStep("空格确认",
                          action=lambda: app.send_space(timeout=15),
                          verify={"auto_id": "1202", "control_type": "Edit"},
                          timeout=20,
                          continue_on_missing=False))

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
    # steps.append(FlowStep("循环读取数据流",
    #                       action=_make_data_flow_loop(app, out_dir, max_flows),
    #                       timeout=1200))

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
            app.click_ctrl(back_btn)
            time.sleep(0.5)
            return True
        log.warning("返回按钮(auto_id=2)不存在")
        return False
    return action


def _make_nav_data_flow(app: DtsApp):
    def action():
        app.send_keys("{DOWN 2}{ENTER}")
        time.sleep(0.5)
        app.send_keys("{DOWN 6}{ENTER}")
        time.sleep(0.5)
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
        # 数据流列表被 DTS 存到桌面 → 拷回 out_dir，供 AI 阶段1 支持清单使用
        _copy_dataflow_list(out_dir, flow_count)
        log.info(f"  数据流{flow_count} 完成")
        app.wait_for_control("1")
        # 弹窗确定
        exit_btn = app.window.child_window(
            auto_id="1", control_type="Button", found_index=0
        )
        if exit_btn.exists(timeout=3):
            app.click_ctrl(exit_btn)

        # ── 读取保存路径 ──
        app.wait_for_control("1058")
        csv = app.extract_csv_path()
        # 把 DTS 导出的 CSV 拷进 out_dir（AI 阶段2/3 的数据源）
        if csv and Path(csv).exists():
            try:
                shutil.copy2(csv, out_dir / f"DataFlow_{flow_count}.csv")
                log.info(f"  ✓ 数据流CSV已保存: DataFlow_{flow_count}.csv")
            except Exception as e:
                log.warning(f"  数据流CSV复制失败: {e}")
        else:
            log.warning(f"  CSV 文件不存在: {csv}")
        exit_btn = app.window.child_window(
            auto_id="1058", control_type="Button", found_index=0
        )
        if exit_btn.exists(timeout=3):
            log.info("点击 csv 路径界面 确认 按钮")
            app.click_ctrl(exit_btn)

        log.info(f"  CSV: {csv}" if csv else "  CSV: 未找到")

        # 返回到读取所有数据流
        back = app.window.child_window(
            auto_id="2", control_type="Button", found_index=0
        )
        log.info("返回到读取所有数据流")
        app.click_ctrl(back)
        # 返回主页
        app.wait_for_control("1129")

        # 切换到下一个数据流: DOWN + ENTER
        log.info("切换到下一个数据流...")
        app.send_keys("{DOWN}")
        time.sleep(0.5)
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
                    app.click_ctrl(cb)
            app.click_ctrl(right_btn)
            time.sleep(0.5)

    # 保存列表
    save_btn = app.window.child_window(
        auto_id="1013", control_type="Button", found_index=0
    )
    log.info("点击 保存列表 按钮")
    app.click_ctrl(save_btn)
    time.sleep(0.5)
    # 保存弹窗出现 → 先激活窗口让弹窗获得焦点，再聚焦文件名输入框，最后输入
    app.focus_active_window()
    if not app.focus_edit_in_dialog(timeout=4):
        log.warning("保存对话框文件名输入框未出现/聚焦失败")
    app.send_keys(f"^a{file_name}{{ENTER}}")

    # 处理覆盖弹窗
    for _ in range(8):
        btn = app.window.child_window(
            title="是(Y)", control_type="Button", found_index=0
        )
        if btn.exists(timeout=0.5):
            app.click_ctrl(btn)
            break
        time.sleep(0.3)
    time.sleep(2)
    app.send_keys("{ENTER}{ENTER}")

    # 载入列表
    load_btn = app.window.child_window(
        auto_id="1118", control_type="Button", found_index=0
    )
    log.info("点击 载入列表 按钮")
    app.click_ctrl(load_btn)
    # 载入(打开)弹窗 → 先激活窗口 + 聚焦文件名输入框，再输入
    app.focus_active_window()
    if not app.focus_edit_in_dialog(timeout=4):
        log.warning("载入对话框文件名输入框未出现/聚焦失败")
    app.send_keys(f"^a{file_name}{{ENTER}}{{ENTER}}{{ENTER}}")
    time.sleep(10)

    # 返回
    back_btn = app.window.child_window(
        auto_id="1042", control_type="Button", found_index=0
    )
    if back_btn.exists(timeout=3):
        log.info("点击 返回 按钮")
        app.click_ctrl(back_btn)
    # 自定义文件名（先聚焦输入框，避免打进主窗口空处）
    app.focus_active_window()
    app.focus_edit_in_dialog(timeout=4)
    app.send_keys(f"{file_name}")
