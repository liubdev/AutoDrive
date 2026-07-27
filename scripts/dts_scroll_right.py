"""
DTS 向右翻页工具 - 独立版

用途: 自动连接 DTS650，点击"向右翻页"按钮 5 次

环境: pip install pywinauto psutil
运行: python dts_scroll_right.py
"""
import time
import psutil
import subprocess
from pywinauto import Application
from pywinauto.findwindows import find_elements

DTS_EXE = r"C:\Program Files (x86)\DTS\DTS20220525\DTS650.exe"


def find_dts_pid():
    """找到 DTS650 的进程 ID"""
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and "dts650" in proc.info["name"].lower():
                return proc.info["pid"]
        except Exception:
            continue
    return None


def find_dts_window():
    """找到 DTS650 主窗口"""
    wins = find_elements(backend="uia", top_level_only=True)
    for w in wins:
        try:
            if w.class_name == "CDTS650MainClass":
                return w
        except Exception:
            continue
    return None


def wait_dts_window(timeout=20):
    """等待 DTS 主窗口出现"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        win = find_dts_window()
        if win:
            return win
        time.sleep(0.5)
    return None


def main():
    print("=" * 40)
    print("  DTS 向右翻页工具")
    print("=" * 40)

    # 1. 启动或连接 DTS
    pid = find_dts_pid()
    if pid:
        print(f"  已连接 DTS (PID={pid})")
    else:
        print("  启动 DTS...")
        subprocess.Popen([DTS_EXE])

    # 2. 等待窗口
    print("  等待窗口...")
    win = wait_dts_window(timeout=20)
    if not win:
        print("  ✗ DTS 窗口未出现")
        return
    print(f"  找到窗口: {win.name} (handle={win.handle})")

    # 3. 连接窗口
    app = Application(backend="uia").connect(handle=win.handle)

    # 4. 点击向右翻页 5 次
    btn = app.top_window().child_window(
        auto_id="DownButton", control_type="Button", found_index=0
    )
    if btn.exists(timeout=3):
        for i in range(5):
            btn.click()
            print(f"  ✓ 第 {i+1}/5 次点击")
            time.sleep(0.5)
        print("  ✓ 翻页完成")
    else:
        print("  ✗ 未找到翻页按钮")

    print("  ✓ 断开连接")


if __name__ == "__main__":
    main()
