#!/usr/bin/env python3
"""后台自动化回归测试：消息式输入层 + DtsApp 后台路由 + 流程接线。

覆盖:
  1. automation.background 键解析/消息构造（不依赖真实窗口）
  2. BaseApp/DtsApp 后台模式路由（send_keys/click_ctrl/click_at/_apply_window_hiding）
  3. build_dts_flow 在后台 DtsApp 上正常构建、步骤动作指向后台路由方法

真机行为（UIA Invoke / PostMessage 对 DTS 控件的实际效果）无法在无 DTS 环境
验证 —— 用打桩断言"路由到了后台路径"，这正是"可支持后台形态"的关键。
"""
import os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\liubo1\Desktop\AutoDrive")

from PySide6.QtCore import QSettings
QSettings("AutoDrive", "AutoDrive").clear()
from config import settings
from automation import background as bg
from automation.apps.dts import DtsApp
from automation.flows.dts_flow import build_dts_flow

ok = True
def check(name, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name)
    ok = ok and cond

# ── 1. 消息式输入层 ─────────────────────────────────
captured = []
bg.user32.PostMessageW = lambda hwnd, m, w, l: captured.append((hwnd, m, w, l)) or 1
bg._get_focus = lambda top: 0x1234
bg.send_keys(0x999, "{DOWN 2}{ENTER}DataFlow_List_1.txt", pause=0.0)
d = [m for _, m, _, _ in captured if m == 0x0100]
u = [m for _, m, _, _ in captured if m == 0x0101]
c = [m for _, m, _, _ in captured if m == 0x0102]
check("按键: DOWN2+ENTER 拆为 3 按", len(d) == 3 and len(u) == 3)
check("按键: 文件名 19 字符 → 19 次 WM_CHAR", len(c) == 19)
check("按键: 全部投到目标句柄", all(h == 0x1234 for h, *_ in captured))

sends = []
bg.user32.SendMessageW = lambda hwnd, m, w, l: sends.append((hwnd, m, w, l)) or 0
bg._deepest_child = lambda top, x, y: 0x777
bg._screen_to_client = lambda hwnd, x, y: (10, 20)
bg.click_at(0x999, 300, 400)
check("坐标点击: MOVE+DOWN+UP 三段", [m for _, m, _, _ in sends] == [0x200, 0x201, 0x202])
check("坐标点击: 客户区 lParam 正确", sends[0][3] == (20 << 16) | 10)

# ── 2. DtsApp 后台路由 ──────────────────────────────
settings.dts_exe = sys.executable  # 真实存在的文件
app = DtsApp()
check("DtsApp.background 默认 True", app.background is True)
check("DtsApp 读取 window_mode/start_minimized/elevated", app.window_mode == "normal")

bg_sent, bg_clicks = [], []
bg.send_keys = lambda hwnd, keys, **kw: (bg_sent.append((hwnd, keys)) or True)
bg.click_ctrl = lambda ctrl, hwnd=None: (bg_clicks.append(True) or True)
bg.move_offscreen = lambda hwnd: (bg._moved.append(hwnd) if hasattr(bg, "_moved") else None) or True

app._window = object()  # 假装已连接
app._app = object()
import types
# 打桩 _hwnd 返回固定句柄
app._hwnd = lambda: 0xAAAA
app.send_keys("{ENTER}")
check("BaseApp.send_keys 后台 → bg.send_keys", bg_sent and bg_sent[-1] == (0xAAAA, "{ENTER}"))
app.click_ctrl("fake_ctrl")
check("BaseApp.click_ctrl 后台 → bg.click_ctrl", bg_clicks == [True])

# _apply_window_hiding → move_offscreen（后台+offscreen 模式，显式切回验证隐藏路径）
app.window_mode = "offscreen"
bg._moved = []
bg.move_offscreen = lambda hwnd: bg._moved.append(hwnd) or True
app._apply_window_hiding()
check("DtsApp._apply_window_hiding → bg.move_offscreen", bg._moved == [0xAAAA])

# 前台模式（dts_background=False）→ 物理路径不崩
from PySide6.QtWidgets import QApplication
_qapp = QApplication([])
settings.dts_background = False
fg = DtsApp()
fg._window = object(); fg._app = object(); fg._hwnd = lambda: 0xBBBB
check("DtsApp 前台模式 background=False", fg.background is False)
settings.dts_background = True

# ── 3. 流程在后台 DtsApp 上构建 ──────────────────────
out = settings.reports_dir  # 已存在
steps = build_dts_flow(DtsApp(), out, max_flows=2)
check("build_dts_flow 构建 15 步", len(steps) == 15)
names = [s.name for s in steps]
check("步骤顺序正确（启动→…→循环读取数据流）",
      names[0] == "启动 DTS" and names[-1] == "循环读取数据流")
check("步骤动作均可调用（闭包构建无异常）", all(callable(s.action) for s in steps))

print(f"== 后台自动化回归 FAIL {0 if ok else 1} ==")
sys.exit(0 if ok else 1)
