"""
DTS 后台自动化输入层 — 窗口定向消息输入

DTS 运行在后台（屏幕外/被遮挡）时，真实鼠标 (click_input) 与全局键盘
(pywinauto.keyboard) 只投递给前台窗口，无法操作它。本模块改用 Win32 消息
直达 DTS 窗口句柄，与前台状态完全解耦：

  - 按键  : AttachThreadInput 取 DTS 焦点控件 → PostMessage WM_KEYDOWN/UP + WM_CHAR
            （只读焦点、不抢前台；解析复用 pywinauto.keyboard.parse_keys）
  - 点击  : UIA Invoke（标准按钮，后台安全）优先；降级为 SendMessage 左键按下/抬起
  - 坐标  : 屏幕坐标 → 最深子窗口客户区 → SendMessage（替代物理 mouse.click）
  - 隐藏  : 移到屏幕外 (-32000,-32000) + 移除任务栏（toolwindow 风格）
  - 置顶  : SetWindowPos(HWND_TOPMOST) + AttachThreadInput + SetForegroundWindow 夺回前台
  - 提权  : schtasks /RL HIGHEST 以管理员启动 DTS，避免 UAC 弹窗

注：依赖 pywinauto 0.6.3 —— 其 keyboard 模块已无模块级 send_keys（旧代码会
ImportError），这里统一改为窗口定向发送，顺带修复该隐患。
"""

import ctypes
import logging
import subprocess
import time
from ctypes import wintypes

import pywinauto.keyboard as kb
from pywinauto.keyboard import KeyAction, VirtualKeyAction

logger = logging.getLogger("autodrive.bg")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── 常量 ──────────────────────────────────────────────
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
MK_LBUTTON = 0x0001

SW_HIDE, SW_SHOW, SW_MINIMIZE, SW_RESTORE = 0, 5, 6, 9
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0004, 0x0010
GWL_EXSTYLE = -20
WS_EX_APPWINDOW, WS_EX_TOOLWINDOW = 0x00040000, 0x00000080
CWP_ALL = 0x0000
MAPVK_VK_TO_VSC = 0

OFFSCREEN_X, OFFSCREEN_Y = -32000, -32000

# 需要 "扩展键" 标志的虚拟键（方向键 / 编辑键 / 右侧修饰键）
_EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24,          # PgUp PgDn End Home
    0x25, 0x26, 0x27, 0x28,          # ← ↑ → ↓
    0x2D, 0x2E,                      # Insert Delete
    0x5B, 0x5C, 0x5D,                # Win WinMenu Apps
    0xA1, 0xA3, 0xA5,                # 右侧 Shift Ctrl Alt
}

# ── Win32 类型声明（64 位指针必须声明，否则句柄截断） ──
def _declare(name, restype, argtypes):
    fn = getattr(user32, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


_declare("GetForegroundWindow", wintypes.HWND, [])
_declare("GetFocus", wintypes.HWND, [])
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []
_declare("GetWindowThreadProcessId", wintypes.DWORD,
         [wintypes.HWND, wintypes.LPDWORD])
_declare("AttachThreadInput", wintypes.BOOL,
         [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL])
_declare("PostMessageW", wintypes.BOOL,
         [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM])
_declare("SendMessageW", ctypes.c_ssize_t,
         [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM])
_declare("ScreenToClient", wintypes.BOOL,
         [wintypes.HWND, ctypes.POINTER(wintypes.POINT)])
_declare("ClientToScreen", wintypes.BOOL,
         [wintypes.HWND, ctypes.POINTER(wintypes.POINT)])
_declare("ChildWindowFromPointEx", wintypes.HWND,
         [wintypes.HWND, wintypes.POINT, wintypes.UINT])
_declare("GetWindowRect", wintypes.BOOL,
         [wintypes.HWND, ctypes.POINTER(wintypes.RECT)])
_declare("SetWindowPos", wintypes.BOOL,
         [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
          ctypes.c_int, ctypes.c_int, wintypes.UINT])
_declare("ShowWindow", wintypes.BOOL, [wintypes.HWND, ctypes.c_int])
_declare("IsIconic", wintypes.BOOL, [wintypes.HWND])
_declare("SetForegroundWindow", wintypes.BOOL, [wintypes.HWND])
_declare("SetFocus", wintypes.HWND, [wintypes.HWND])
_declare("GetWindowLongPtrW", ctypes.c_ssize_t,
         [wintypes.HWND, ctypes.c_int])
_declare("SetWindowLongPtrW", ctypes.c_ssize_t,
         [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t])
_declare("MapVirtualKeyW", wintypes.UINT, [wintypes.UINT, wintypes.UINT])


# ═══════════════════════════════════════════════════════
#  按键（窗口定向，不依赖前台）
# ═══════════════════════════════════════════════════════

def _key_lparam(vk: int, is_up: bool, extended: bool) -> int:
    """构造 WM_KEYDOWN/UP 的 lParam（扫描码 + 扩展位 + 过渡位）"""
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    lp = 1 | (scan << 16)                 # 重复次数 1 + 扫描码
    if extended:
        lp |= 0x01000000                  # 扩展键标志
    if is_up:
        lp |= 0xC0000000                  # 前一键已按 + 过渡位
    return lp


def _post_key_action(hwnd, act):
    """把一个 parse_keys 动作投递为 PostMessage 消息"""
    if isinstance(act, VirtualKeyAction):
        vk = int(act.key)
        ext = vk in _EXTENDED_VKS
        if act.down:
            user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _key_lparam(vk, False, ext))
        if act.up:
            user32.PostMessageW(hwnd, WM_KEYUP, vk, _key_lparam(vk, True, ext))
    elif isinstance(act, KeyAction):
        # 字符直接用 WM_CHAR —— Edit 控件原生处理大小写/字符集
        user32.PostMessageW(hwnd, WM_CHAR, ord(act.key), 1)


def _get_focus(hwnd_top: int):
    """AttachThreadInput 后读取 DTS 线程当前焦点控件（不抢前台）。

    校验返回句柄确属 DTS 进程，否则退回顶层窗口 —— 避免误投到我们自己。
    """
    dts_thread = user32.GetWindowThreadProcessId(hwnd_top, None)
    cur = kernel32.GetCurrentThreadId()
    if dts_thread and dts_thread != cur:
        user32.AttachThreadInput(cur, dts_thread, True)
        try:
            focus = user32.GetFocus()
        finally:
            user32.AttachThreadInput(cur, dts_thread, False)
        if focus:
            t = user32.GetWindowThreadProcessId(focus, None)
            if t == dts_thread:
                return focus
    return hwnd_top


def set_focus(hwnd: int) -> bool:
    """AttachThreadInput + SetFocus 给 DTS 窗口设键盘焦点（不置前台）"""
    if not hwnd:
        return False
    dts_thread = user32.GetWindowThreadProcessId(hwnd, None)
    cur = kernel32.GetCurrentThreadId()
    if dts_thread and dts_thread != cur:
        if user32.AttachThreadInput(cur, dts_thread, True):
            try:
                user32.SetFocus(hwnd)
                logger.debug("已设键盘焦点 0x%X", hwnd)
                return True
            finally:
                user32.AttachThreadInput(cur, dts_thread, False)
    return False


def send_keys(hwnd_top: int, keys: str, pause: float = 0.05) -> bool:
    """向 DTS 窗口投递键盘输入（pywinauto 语法，如 '{DOWN 2}{ENTER}' / 文件名）"""
    if not hwnd_top:
        return False
    target = _get_focus(hwnd_top)
    if target == hwnd_top:
        # 顶层窗口没有子控件持有键盘焦点 → ENTER/SPACE 等导航键不会触发
        # 默认按钮。后台安全地给顶层窗口设焦点（不激活、不抢前台），再投递。
        set_focus(hwnd_top)
        logger.debug("无子控件焦点，已为顶层窗口 0x%X 建立焦点", hwnd_top)
    try:
        actions = kb.parse_keys(keys)
    except Exception as e:  # noqa: BLE001
        logger.warning("解析按键失败 %r: %s", keys, e)
        return False
    for act in actions:
        try:
            _post_key_action(target, act)
        except Exception as e:  # noqa: BLE001
            logger.warning("投递按键失败 %r: %s", act, e)
        time.sleep(pause)
    logger.info("按键 %r → 窗口0x%X (焦点0x%X)", keys, hwnd_top, target)
    return True


# ═══════════════════════════════════════════════════════
#  点击（UIA Invoke / SendMessage，均后台安全）
# ═══════════════════════════════════════════════════════

def _screen_to_client(hwnd: int, sx: int, sy: int):
    pt = wintypes.POINT(sx, sy)
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def _deepest_child(hwnd_top: int, sx: int, sy: int):
    """找屏幕点 (sx,sy) 下的最深子窗口（模拟真实鼠标命中测试）"""
    cx, cy = _screen_to_client(hwnd_top, sx, sy)
    pt = wintypes.POINT(cx, cy)
    child = user32.ChildWindowFromPointEx(hwnd_top, pt, CWP_ALL)
    return child or hwnd_top


def click_at(hwnd_top: int, sx: int, sy: int) -> bool:
    """屏幕坐标 → 消息式左键单击（替代物理 mouse.click）"""
    if not hwnd_top:
        return False
    target = _deepest_child(hwnd_top, sx, sy)
    cx, cy = _screen_to_client(target, sx, sy)
    lp = (cy << 16) | (cx & 0xFFFF)
    user32.SendMessageW(target, WM_MOUSEMOVE, 0, lp)
    user32.SendMessageW(target, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    user32.SendMessageW(target, WM_LBUTTONUP, 0, lp)
    logger.info("坐标点击 (%d,%d) → 子窗口0x%X 客户区(%d,%d)", sx, sy, target, cx, cy)
    return True


def click_ctrl(ctrl, hwnd_top: int = None) -> bool:
    """后台点击 pywinauto 控件：UIA Invoke 优先，失败降级为坐标消息点击。

    标准 MFC 按钮 (ButtonWrapper) 走 InvokePattern，最小化/屏幕外均有效。
    """
    try:
        ctrl.click()          # UIA Invoke —— 后台安全
        logger.debug("UIA Invoke 点击成功")
        return True
    except Exception:          # noqa: BLE001
        pass
    try:
        r = ctrl.rectangle()
        cx, cy = (r.left + r.width() // 2), (r.top + r.height() // 2)
        if hwnd_top is None:
            hwnd_top = ctrl.wrapper_object().element_info.handle or int(ctrl.handle)
        logger.info("UIA Invoke 失败 → 降级坐标点击 (%d,%d)", cx, cy)
        return click_at(hwnd_top, cx, cy)
    except Exception:          # noqa: BLE001
        logger.warning("控件点击失败（UIA Invoke 与坐标降级均失败）")
        return False


# ═══════════════════════════════════════════════════════
#  窗口管理（隐藏 / 置顶 / 前台）
# ═══════════════════════════════════════════════════════

def _set_toolwindow(hwnd: int):
    """从任务栏移除（去 APPWINDOW、加 TOOLWINDOW）"""
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style &= ~WS_EX_APPWINDOW
    style |= WS_EX_TOOLWINDOW
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)


def move_offscreen(hwnd: int) -> bool:
    """窗口移到屏幕外并隐藏任务栏按钮（保持原尺寸，功能不变）"""
    if not hwnd:
        return False
    try:
        _set_toolwindow(hwnd)
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w = r.right - r.left
        h = r.bottom - r.top
        user32.SetWindowPos(hwnd, 0, OFFSCREEN_X, OFFSCREEN_Y, w, h,
                            SWP_NOZORDER | SWP_NOACTIVATE)
        logger.info("窗口 0x%X 已移到屏幕外并隐藏任务栏", hwnd)
        return True
    except Exception as e:    # noqa: BLE001
        logger.warning("移出屏幕失败: %s", e)
        return False


def minimize(hwnd: int) -> bool:
    if hwnd:
        return bool(user32.ShowWindow(hwnd, SW_MINIMIZE))
    return False


def is_minimized(hwnd: int) -> bool:
    return bool(hwnd and user32.IsIconic(hwnd))


def set_topmost(hwnd: int, on: bool = True) -> bool:
    """置顶 / 取消置顶（不改变大小位置）"""
    if not hwnd:
        return False
    flag = HWND_TOPMOST if on else HWND_NOTOPMOST
    ok = bool(user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0,
                                  SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))
    logger.debug("置顶 %s 0x%X", "开" if on else "关", hwnd)
    return ok


def active_window() -> int:
    return user32.GetForegroundWindow() or 0


def is_active(hwnd: int) -> bool:
    return bool(hwnd) and user32.GetForegroundWindow() == hwnd


def force_foreground(hwnd: int) -> bool:
    """AttachThreadInput + SetForegroundWindow 夺回前台（绕开焦点限制）"""
    if not hwnd:
        return False
    if user32.GetForegroundWindow() == hwnd:
        return True
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    cur = kernel32.GetCurrentThreadId()
    attached = False
    if fg_thread and fg_thread != cur:
        attached = bool(user32.AttachThreadInput(cur, fg_thread, True))
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetForegroundWindow(hwnd))
        logger.debug("夺回前台 0x%X: %s", hwnd, "成功" if ok else "失败")
        return ok
    finally:
        if attached:
            user32.AttachThreadInput(cur, fg_thread, False)


# ═══════════════════════════════════════════════════════
#  启动（最小化 / 提权免 UAC）
# ═══════════════════════════════════════════════════════

def launch(exe: str, cwd: str = None, minimized: bool = True):
    """启动 DTS；minimized=True 时用 STARTUPINFO 直接最小化启动"""
    si = subprocess.STARTUPINFO()
    if minimized:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = SW_MINIMIZE
    p = subprocess.Popen([exe], cwd=cwd, startupinfo=si)
    logger.info("已启动 %s (PID=%s, minimized=%s)", exe, p.pid, minimized)
    return p


def launch_elevated(exe: str):
    """用计划任务以最高权限启动 DTS，避免 UAC 弹窗。

    失败（无权限/策略限制）返回 None，由调用方回退普通启动。
    """
    task = "AutoDrive_DTS650"
    tr = f'"{exe}"'
    r1 = subprocess.run(
        ["schtasks", "/create", "/f", "/tn", task, "/tr", tr,
         "/sc", "once", "/st", "00:00", "/rl", "highest"],
        capture_output=True, text=True)
    if r1.returncode != 0:
        logger.warning("创建提权计划任务失败: %s", r1.stderr.strip())
        return None
    r2 = subprocess.run(["schtasks", "/run", "/tn", task],
                        capture_output=True, text=True)
    if r2.returncode != 0:
        logger.warning("运行提权计划任务失败: %s", r2.stderr.strip())
        return None
    logger.info("已通过计划任务以管理员启动: %s", exe)
    return task
