"""
DTS 自动控制
"""

import sys, logging, warnings, time, re
from pathlib import Path
from automation.apps.dts import DtsApp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("run_dts")


def handle_overwrite_dialog(timeout=4):
    """
    检测文件覆盖弹窗，出现时点击"是"确认覆盖

    弹窗在 DTS 窗口内部（非独立顶层窗口），需全范围搜索。
    特征: 含文字"已存在"，按钮"是(Y)" 或 "是(&Y)"
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            btn = app.window.child_window(
                title="是(Y)", control_type="Button", found_index=0
            )
            if btn.exists(timeout=0.5):
                btn.click()
                print("  ✓ 确认覆盖")
                return True

            btn2 = app.window.child_window(
                title="是(Y)", control_type="Button", found_index=0
            )
            if btn2.exists(timeout=0.5):
                btn2.click()
                print("  ✓ 确认覆盖")
                return True
        except Exception:
            app.send_keys("Y")
            time.sleep(0.5)
            app.send_keys("{ENTER}")
        time.sleep(0.3)
    return False


# ── 第1步: 启动 ──
log.info("=" * 40)
log.info("  DTS 自动控制")
log.info("=" * 40)
log.info("")
log.info("[第1步] 启动 DTS...")

app = DtsApp()
if not app.ensure_running(timeout=30):
    log.info("  x 启动失败")
    exit(1)
log.info("  √ DTS 已启动")

log.info("确认弹窗处理")
log.info("[第2步] 点击确认弹窗处理...")
if app.confirm(timeout=15):
    log.info("  √ 已点击确认")
else:
    log.info("  x 点击确认失败")

log.info("[第3步] 一键进入...")
if app.one_click_enter(timeout=15):
    log.info("  √ 已进入")
else:
    log.info("  x 进入失败")

time.sleep(5)
log.info("[第5步] 点击进入系统...")
if app.enter_system(timeout=15):
    log.info("  √ 已点击进入系统")
else:
    log.info("  x 点击进入系统失败")

# 等待数据加载
time.sleep(12)
log.info("[第6步] 通过回车控制发动机系统诊断...")
if app.send_enter(timeout=15):
    log.info("  √ 诊断完成")
else:
    log.info("  x 诊断失败")

# 扫描设备进去到下一步
time.sleep(12)
log.info("[第7步] 通过检车结果发送空格指令进去下一步...")
if app.send_space(timeout=15):
    log.info("  √ 指令发送成功")
else:
    log.info("  x 指令发送失败")

# 发动机2.0
time.sleep(12)
log.info("[第8步] 通过回车控制发动机2.0T 马力L D样件")
if app.send_enter(timeout=15):
    log.info("  √ 诊断完成")
else:
    log.info("  x 诊断失败")

# 系统提示：注意：由于大通厂家设计逻辑原因,.... 第一个空格确认
if app.send_space(timeout=15):
    log.info("  √ 指令发送成功")
else:
    log.info("  x 指令发送失败")
# 等待第二个版本信息出现保存。

path = app.save_info_to_txt("d:/info.txt")
if path:
    print(f"已保存: {path}")

# 点击空格确认
if app.send_space(timeout=15):
    log.info("  √ 指令发送成功")
else:
    log.info("  x 指令发送失败")


# p8 1.读数据流
app.send_keys("{DOWN 2}")
app.send_keys("{ENTER}")
time.sleep(2)

# 2. 读取所有数据
app.send_keys("{DOWN 6}")
app.send_keys("{ENTER}")
time.sleep(2)

# 3. 进入数据流1
app.send_keys("{ENTER}")
time.sleep(2)


# p9 右滑选择 + 勾选全选
def check_all():
    """勾选所有未选的'全选'复选框"""
    for auto_id in ["1070", "1073"]:
        try:
            cb = app.window.child_window(
                auto_id=auto_id, control_type="CheckBox", found_index=0
            )
            if cb.exists(timeout=0.5) and cb.get_toggle_state() == 0:
                cb.click()
                print(f"    ✓ 勾选 auto_id={auto_id}")
        except Exception:
            continue


right_btn = app.window.child_window(
    auto_id="DownButton", control_type="Button", found_index=0
)
if right_btn.exists(timeout=3):
    for i in range(12):
        check_all()
        right_btn.click()
        print(f"  ✓ 第{i+1}次翻页")
        time.sleep(0.5)
    check_all()


def safe_click(ctrl, name="按钮"):
    """安全点击，先 click_input 失败后降级 click"""
    try:
        ctrl.click_input()
        print(f"  ✓ 点击{name}")
        return True
    except Exception:
        try:
            ctrl.click()
            print(f"  ✓ 点击{name}(click)")
            return True
        except Exception as e:
            print(f"  ✗ 点击{name}失败: {e}")
            return False


# 保存列表
save_btn = app.window.child_window(auto_id="1013", control_type="Button", found_index=0)
if save_btn.exists(timeout=3):
    safe_click(save_btn, "保存列表")

# 输入文本内容 然后回车
time.sleep(0.5)
app.send_keys("DataFlow_List_All.txt")
time.sleep(0.5)
app.send_keys("{ENTER}")
# 如果文件已存在，确认覆盖
handle_overwrite_dialog()

# 载入列表
load_btn = app.window.child_window(auto_id="1118", control_type="Button", found_index=0)
if load_btn.exists(timeout=3):
    safe_click(load_btn, "载入列表")
# 输入文本内容 然后回车
app.send_keys("DataFlow_List_All.txt")
time.sleep(0.5)
app.send_keys("{ENTER}")
time.sleep(0.5)
app.send_keys("{ENTER}")
time.sleep(10)

# 点击返回
back_btn = app.window.child_window(auto_id="1042", control_type="Button", found_index=0)
if back_btn.exists(timeout=3):
    safe_click(back_btn, "返回")
time.sleep(12)
# 记录名称
exit_tip = app.window.child_window(auto_id="1", control_type="Button", found_index=0)
if exit_tip.exists(timeout=3):
    safe_click(exit_tip, "确认")

time.sleep(1)

# 找日志控件
edit = app.window.child_window(auto_id="1202", control_type="Edit")
text = edit.legacy_properties()["Value"]


match = re.search(r"[A-Za-z]:\\.*?\.csv", text)

if match:
    csv_path = match.group(0)
    print(csv_path)
else:
    print("没有找到CSV路径")

# ── 完成 ──
log.info("")
log.info("[完成] 断开连接")
app.disconnect()
