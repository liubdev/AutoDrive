"""
DTS 应用自动化模块

自绘按钮定位策略（跨分辨率自适应）:
  A. UIA 文字查找 → 最稳（标准控件）
  B. 图片模板匹配 → 无文字图片按钮
  C. 锚点相对比例 → 自绘按钮（非像素偏移）

后台模式（settings.dts_background=True，默认）:
  DTS 全程在后台运行 —— 输入走 automation.background 消息式投递
  （UIA Invoke / PostMessage / SendMessage），窗口被移到屏幕外并去掉任务栏，
  用户看不到任何执行过程。前台模式回退旧物理输入。

锚点控件信息:
  - "当前设置:车下使用" 文本 (auto_id=1185)  → 宽1880 高38
  - "上翻页" 按钮       (auto_id=1013)        → 宽178
"""

import logging
import time
from datetime import datetime
from typing import Optional
from pywinauto.findwindows import find_elements

from . import BaseApp
from automation import background as bg
from config import settings

logger = logging.getLogger("autocar.apps.dts")


class DtsApp(BaseApp):
    INSTANCE_MULTI = False
    # 默认后台；实例化时从 settings 读取（可在 data/config.json 配置 dts_background=False 回退）
    BACKGROUND = True
    # 窗口连接自愈：同一失效期内两次重连的最小间隔（秒），防重连风暴
    _RECONNECT_COOLDOWN = 3.0

    def __init__(self):
        super().__init__()
        # DTS650 路径唯一来源：settings.dts_exe（默认值定义在 config/settings.py，
        # 首次运行自动生成 data/config.json 模板，可在其中覆盖）
        self.APP_EXE = settings.dts_exe
        self.background = getattr(settings, "dts_background", True)
        self.window_mode = getattr(settings, "dts_window_mode", "offscreen")
        self.start_minimized = getattr(settings, "dts_start_minimized", True)
        self.elevated = getattr(settings, "dts_elevated", False)
        # 上一次自动重连时刻（0=从未）；窗口自愈用
        self._last_reconnect_at = 0.0

    # ── 窗口连接自愈 ──────────────────────────────────

    def _window_stale(self, win) -> bool:
        """self._window 包装是否失效（UIA 连接断开后元素句柄抛 COM -2147220991）。

        只对真实 pywinauto 包装判失效（类上有 element_info/handle）；测试桩/伪造
        对象没有这两个名字则直接放行、不重连。用 dir() 而非 hasattr —— pywinauto
        的 element_info 可能是取值时抛错的 property，hasattr 会把它误判为不存在。
        """
        try:
            if "element_info" not in dir(win) and "handle" not in dir(win):
                return False
        except Exception:      # noqa: BLE001
            return True
        try:
            _ = win.handle
            return False
        except Exception:      # noqa: BLE001
            return True

    @property
    def window(self):
        """顶层窗口包装；后台模式下检测到连接失效时自动重连 DTS 主窗口。

        DTS 长时间交互 + 模态弹窗循环后，pywinauto 缓存的 UIA 元素可能失效
        （handle 访问抛 0x80040201），此后所有 child_window/exists/click 都会崩
        —— 旧代码直接中止流程。这里在每次取 window 时做轻量存活检查（读 handle），
        失效即调 _reconnect_main 重建连接，用冷却时间避免同一失效期内的重连风暴。
        """
        win = super().window
        if (win is not None and self.background and self._window_stale(win)
                and time.time() - self._last_reconnect_at >= self._RECONNECT_COOLDOWN):
            self._last_reconnect_at = time.time()
            logger.warning("窗口连接失效（UIA 句柄失效），自动重连 DTS 主窗口…")
            self._reconnect_main(timeout=8)
            win = self._window
        return win

    # ── 后台窗口隐藏 ──────────────────────────────────

    def _apply_window_hiding(self):
        """后台模式：把当前连接窗口移到屏幕外 + 去任务栏（功能不受影响）。

        幂等，_reconnect_main 每次连接后都会调用，天然覆盖后续出现的窗口。
        """
        if not self.background or self.window_mode != "offscreen":
            return
        hwnd = self._hwnd()
        if hwnd:
            bg.move_offscreen(hwnd)

    # ── 启动确认（UIA 标准控件） ────────────────────

    def confirm(self, timeout: int = 30) -> bool:
        if not self.window and not self._wait_for_dts_window(timeout):
            return False
        btn = self.window.child_window(auto_id="1", control_type="Button")
        if btn.exists(timeout=3):
            # 后台：先把确认弹窗也隐藏到屏幕外，用户全程看不到
            self._apply_window_hiding()
            self.click_ctrl(btn)
            logger.info("确认")
            return True
        return False

    # ── 一键进入 ──
    # 锚点: "上翻页" 按钮 (auto_id=1013)  按钮宽178
    # 目标: (123,170) → rx=102/178=0.573, 内容区比例 ry=170/955=0.178

    def one_click_enter(self, timeout: int = 30) -> bool:
        if not self._reconnect_main(timeout):
            return False
        return self._click_until_control(
            name="一键进入",
            click=lambda: self._click_image_btn(rx=0.573, ry=0.178),
            verify_auto_id="6",
            attempts=3,
            verify_timeout=5,
        )

    # ── 点击进入系统 ──
    # 锚点: "当前设置:车下使用" 文本 (auto_id=1185)  宽1880 高38
    # 目标: (145,152) → rx=(145-20)/1880=0.066, ry=(152-89)/38=1.66

    def enter_system(self, timeout: int = 30) -> bool:
        if not self._reconnect_main(timeout):
            return False
        return self._click_until_control(
            name="点击进入系统",
            click=lambda: self._click_below_text(auto_id="1185", rx=0.066, ry=1.66),
            verify_auto_id="1046",
            attempts=3,
            verify_timeout=5,
        )

    # ── 发动机系统诊断（选项已默认选中，直接 Enter） ──

    def diagnose_engine_system(self, timeout: int = 30) -> bool:
        if not self._reconnect_main(timeout):
            return False
        logger.info("发动机系统诊断: Enter")
        super().send_enter()
        time.sleep(2)
        return True

    # ── 发送指令（先重连，兼容旧脚本） ──────────────

    def send_enter(self, timeout: int = 15) -> bool:
        if not self._reconnect_main(timeout):
            return False
        super().send_enter()
        time.sleep(2)
        return True

    def send_space(self, timeout: int = 15) -> bool:
        if not self._reconnect_main(timeout):
            return False
        super().send_space()
        time.sleep(2)
        return True

    # ── 读取控件文本（通用方法） ────────────────────

    def _read_edit_text(self, auto_id: str = "1202") -> Optional[str]:
        """读取 Edit 控件的文本，多重降级"""
        edit = self.window.child_window(
            auto_id=auto_id, control_type="Edit", found_index=0
        )
        if not edit.exists(timeout=3):
            return None
        # legacy_properties()["Value"] 对 Edit 控件最稳
        try:
            return edit.legacy_properties().get("Value", "")
        except Exception:
            pass
        try:
            return edit.window_text()
        except Exception:
            pass
        try:
            return edit.texts()[0]
        except Exception:
            pass
        return None

    # ── 保存完整信息到 txt ─────────────────────────

    def save_info_to_txt(self, output: str = None) -> Optional[str]:
        """保存 auto_id=1202 的完整文本到文件"""
        text = self._read_edit_text()
        if not text:
            logger.warning("未找到诊断信息")
            return None
        if output is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(settings.reports_dir / f"dtc_{ts}.txt")
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"已保存: {output}")
        return output

    # ── 获取列表第一个项目名称（用于判断当前数据流） ──

    def get_first_list_item(self, timeout: int = 5) -> Optional[str]:
        """
        获取当前列表中第一个 ListItem 的名称

        用于判断进入的数据流是否是同一个（内容相同则跳过）。

        多策略查找:
          1. auto_id="ListViewItem-0" (早期版本)
          2. 任意第一个 ListItem (通用)
          3. 等待列表加载后重试
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            # 策略1: 按 auto_id 找
            try:
                item = self.window.child_window(
                    auto_id="ListViewItem-0", control_type="ListItem", found_index=0
                )
                if item.exists(timeout=0.5):
                    name = item.window_text()
                    logger.info(f"列表第一项: {name}")
                    return name
            except Exception:
                pass

            # 策略2: 找任意第一个 ListItem
            try:
                items = self.window.descendants(control_type="ListItem")
                if items:
                    name = items[0].window_text()
                    logger.info(f"列表第一项(通用): {name}")
                    return name
            except Exception:
                pass

            time.sleep(0.5)

        logger.warning("获取列表第一项失败: 未找到 ListItem")
        # self._dump_list_pane()   # 诊断：列表窗格 1131 是否存在 / 有无 ListItem
        return None

    # ── 调试：UI 状态快照（dts_debug_pause_nav 开启时由流程调用） ──

    def dump_ui_state(self, tag: str = "") -> None:
        """打印当前 DTS 界面状态快照，用于判断导航/按键焦点是否正确。

        前台窗口 → 键盘焦点 → 主窗浅层 UIA 树 → 数据流列表窗格。
        仅在 settings.dts_debug_pause_nav 开启时调用（一次性，允许秒级耗时）；
        任何一步失败都不中断，保证快照总是能完整打出。
        """
        logger.info("════ UI 状态快照: %s ════", tag)
        try:
            fg = bg.active_window()
            logger.info("前台窗口 0x%X pid=%s 类=%s 标题=%r",
                        fg, bg.window_pid(fg), bg.window_class(fg), bg.window_title(fg)[:60])
            hwnd = self._hwnd()
            logger.info("DTS 主窗口 0x%X 类=%s 标题=%r",
                        hwnd, bg.window_class(hwnd), bg.window_title(hwnd)[:60])
            focus = bg._get_focus(hwnd)
            logger.info("键盘焦点 0x%X 类=%s 标题=%r  （类==主窗口类 → 无子控件持焦点，DOWN/ENTER 会落到窗框上）",
                        focus, bg.window_class(focus), bg.window_title(focus)[:60])
            self._dump_window_tree(hwnd)
            self._dump_list_pane()
        except Exception as e:  # noqa: BLE001
            logger.warning("UI 状态快照异常: %s", e)
        logger.info("════ 状态快照结束 ════")

    def _dump_window_tree(self, hwnd: int, max_depth: int = 4, max_nodes: int = 80) -> None:
        """浅层 UIA 树 dump：看当前停在哪个界面、有没有列表/菜单控件。"""
        if not hwnd:
            logger.info("  （未连接主窗口，跳过 UIA 树）")
            return
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd)
        except Exception as e:  # noqa: BLE001
            logger.warning("  UIA 树获取失败: %s", e)
            return
        nodes = [0]

        def _walk(ctrl, depth):
            if nodes[0] >= max_nodes:
                return
            try:
                info = ctrl.element_info
                ct = getattr(info, "control_type", "") or ""
                aid = getattr(info, "automation_id", "") or ""
                cls = getattr(info, "class_name", "") or ""
                name = (ctrl.window_text() or "").strip()[:30]
                r = ctrl.rectangle()
                geo = f"({r.left},{r.top} {r.width()}x{r.height()})" if r.width() else ""
                logger.info("  %s%s type=%s auto_id=%r class=%s %s 名称=%r",
                            "  " * depth, depth, ct, aid, cls, geo, name)
                nodes[0] += 1
            except Exception:
                pass
            if depth < max_depth:
                try:
                    for c in ctrl.children()[:25]:
                        _walk(c, depth + 1)
                except Exception:
                    pass

        try:
            for c in root.children()[:25]:
                _walk(c, 1)
        except Exception:
            pass
        if nodes[0] == 0:
            logger.info("  （UIA 树为空 —— 当前界面可能不是标准控件）")

    def _dump_list_pane(self) -> None:
        """诊断数据流列表窗格 auto_id=1131：是否存在、可见性、子控件类型统计。"""
        if not self.window:
            logger.info("  （未连接窗口，跳过列表窗格诊断）")
            return
        try:
            pane = self.window.child_window(
                auto_id="1131", control_type="Pane", found_index=0
            )
            if not pane.exists(timeout=1):
                logger.info("  列表窗格 auto_id=1131 不存在 —— 当前界面没有可读列表（可能不在数据流菜单）")
                return
            r = pane.rectangle()
            kids = pane.children()
            types = {}
            for c in kids[:30]:
                try:
                    t = c.element_info.control_type
                    types[t] = types.get(t, 0) + 1
                except Exception:
                    pass
            li = pane.descendants(control_type="ListItem")
            logger.info("  列表窗格 1131: %sx%s @(%s,%s) 直接子控件 %d 个 类型=%s ListItem=%d 个",
                        r.width(), r.height(), r.left, r.top, len(kids), types or "{}", len(li))
        except Exception as e:  # noqa: BLE001
            logger.warning("  列表窗格诊断失败: %s", e)

    # ── 提取 CSV 路径 ──────────────────────────────

    def extract_csv_path(self, auto_id: str = "1202") -> Optional[str]:
        """从控件文本中用正则提取 CSV 文件路径"""
        text = self._read_edit_text(auto_id)
        if not text:
            return None
        # 匹配各类路径: C:\xxx\yyy.csv 或 D:/xxx/yyy.csv
        import re

        match = re.search(r"[A-Za-z]:[\\/].*?\.csv", text)
        if match:
            return match.group(0)
        # 降级: 取最后一行（可能是路径）
        lines = text.strip().split("\n")
        last = lines[-1].strip()
        if ".csv" in last or ".txt" in last:
            return last
        return None

    # ── 逐行复制（不确定行数，复制到内容重复为止） ─────

    def focus_active_window(self, timeout: int = 8) -> bool:
        """把 DTS 当前窗口置为活动（后台模式也执行）。

        后台模式 DTS 常驻后台、从不激活：弹窗（保存/载入/确认）打开后系统不会
        给其输入框分配键盘焦点，PostMessage 按键会投到主窗口/旧焦点上而无效。
        本方法把 DTS 主窗口置为活动（AttachThreadInput + SetForegroundWindow；
        modal 弹窗由所有者继承激活；AutoDrive 是 topmost，视觉上 DTS 仍被盖住），
        弹窗激活后系统才会给其默认输入框分配焦点。

        只激活已连接的主窗口（_hwnd()）—— 比按进程枚举全部顶层窗口快得多
        （find_elements 全量 UIA 枚举一次耗数秒），且 modal 弹窗无需逐个激活。
        """
        if not self.background:
            return bool(self.window and self.window.set_focus())
        hwnd = self._hwnd()
        if hwnd and bg.force_foreground(hwnd):
            time.sleep(1)
            return True
        return False

    def _dts_foreground_window(self) -> int:
        """DTS 当前活动顶层窗口句柄（GetForegroundWindow + pid 校验，无 UIA 枚举）。

        保存/载入弹窗（如「保存列表」）打开后即成为活动窗口 → 前台窗口就是弹窗
        本身，直接搜它的 Edit。前台不是 DTS 时回退主窗口。
        """
        fg = bg.active_window()
        if fg and self.pid:
            try:
                if bg.window_pid(fg) == self.pid:
                    return fg
            except Exception:
                pass
        return self._hwnd()

    def _edit_search_windows(self) -> list:
        """搜索文件名输入框的窗口候选：活动弹窗优先，其次主窗口，去重。"""
        hwnds = []
        for h in (self._dts_foreground_window(), self._hwnd()):
            if h and h not in hwnds:
                hwnds.append(h)
        return hwnds

    def _focus_first_edit(self, hwnd: int) -> bool:
        """在指定顶层窗口下找第一个可见 Edit 并线程级 SetFocus；成功打日志。"""
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd)
            edit = root.child_window(control_type="Edit", found_index=0)
            if edit.exists(timeout=0.5):
                r = edit.rectangle()
                if r.width() > 0 and r.height() > 0:   # 可见
                    if self.set_focus_bg(edit):
                        time.sleep(0.3)
                        logger.info("已聚焦文件名输入框")
                        return True
        except Exception:
            pass
        return False

    def focus_edit_in_dialog(self, timeout: int = 5) -> bool:
        """等弹窗（保存/载入，标题如「保存列表」）的文件名输入框出现并聚焦。

        保存弹窗是 DTS 独立的顶层窗口，不在主窗口 self.window 的子树里 ——
        先激活 DTS 使其成为活动窗口，再优先在活动弹窗里找 Edit，找不到才回退
        主窗口。之后 send_keys 的文件名才会落到输入框，而不是打进主窗口空处。
        """
        self.focus_active_window()
        deadline = time.time() + timeout
        while time.time() < deadline:
            for hwnd in self._edit_search_windows():
                if hwnd and self._focus_first_edit(hwnd):
                    return True
            time.sleep(0.5)
        logger.warning("弹窗文件名输入框未在 %ds 内出现/聚焦", timeout)
        return False

    # ── 文件对话框（保存/载入列表）驱动 ───────────────

    def _fg_dialog(self) -> int:
        """前台若是 DTS 的 #32770 弹窗（≠主窗）返回其句柄，否则 0。

        覆盖/确认弹窗与保存/载入文件对话框都是独立顶层 #32770（不在主窗
        self.window 子树里）—— 在主窗口里按 title="是(Y)" 搜索永远找不到。
        一律改用前台窗口判断：谁在前台，谁就是当前要处理的弹窗。
        """
        fg = bg.active_window()
        if (fg and fg != self._hwnd() and self.pid
                and bg.window_pid(fg) == self.pid
                and bg.window_class(fg) == "#32770"):
            return fg
        return 0

    def wait_fg_dialog(self, wait: float = 2.5, exclude=None) -> int:
        """等一个 DTS #32770 弹窗成为前台（确认/覆盖弹窗出现），返回句柄。

        文件对话框回车后，覆盖/确认弹窗可能延迟几百毫秒才弹出 —— 这里轮询
        前台窗口，前台不是 DTS 时降级枚举 DTS 顶层弹窗；超时返回 0。
        """
        exclude = set(exclude or [])
        deadline = time.time() + wait
        while time.time() < deadline:
            dlg = self._fg_dialog()
            if dlg and dlg not in exclude:
                return dlg
            for w in find_elements(backend="uia", top_level_only=True):
                try:
                    hwnd = int(w.handle)
                    if (hwnd not in exclude
                            and self.pid
                            and w.process_id == self.pid
                            and w.class_name == "#32770"):
                        return hwnd
                except Exception:
                    continue
            time.sleep(0.25)
        return 0

    def wait_dts_dialog_by_title(self, title_keywords, wait: float = 8) -> int:
        """按标题等待顶层 #32770 文件弹窗，不依赖系统前台窗口。

        保存/载入列表弹窗肉眼可见时，AutoDrive 可能仍保持 topmost/foreground。
        文件弹窗也可能由 DTS 子进程创建，ProcessId 不等于主窗口 self.pid。
        这里直接枚举顶层对话框并读取 TitleBar.Value，避免误按 PID 过滤掉弹窗。
        """
        if isinstance(title_keywords, str):
            title_keywords = [title_keywords]
        deadline = time.time() + wait
        while time.time() < deadline:
            hwnd = self._find_top_level_dialog_by_title(title_keywords)
            if hwnd:
                return hwnd
            hwnd = self._find_nested_dialog_by_title(title_keywords)
            if hwnd:
                return hwnd
            time.sleep(0.25)
        logger.warning("DTS 文件对话框未在 %.1fs 内出现，标题关键字=%s",
                       wait, title_keywords)
        return 0

    def _title_matches(self, titles: list, title_keywords) -> bool:
        return any(k in title for k in title_keywords for title in titles)

    def _find_top_level_dialog_by_title(self, title_keywords) -> int:
        """查顶层 #32770 弹窗。"""
        for w in find_elements(backend="uia", top_level_only=True):
            try:
                if w.class_name != "#32770":
                    continue
                hwnd = int(w.handle)
                titles = self._dialog_titles(hwnd, w)
                if self._title_matches(titles, title_keywords):
                    logger.info("检测到顶层 DTS 文件对话框 0x%X pid=%s title=%r",
                                hwnd, w.process_id, titles)
                    return hwnd
            except Exception:
                continue
        return 0

    def _find_nested_dialog_by_title(self, title_keywords) -> int:
        """查 DTS 主窗口子树里的 TitleBar，再回溯到所属 #32770 对话框。"""
        hwnd = self._hwnd()
        if not hwnd:
            return 0
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd)
            titlebars = root.descendants(control_type="TitleBar")
        except Exception:
            return 0
        for titlebar in titlebars:
            try:
                titles = self._control_titles(titlebar)
                if not self._title_matches(titles, title_keywords):
                    continue
                dlg = self._ancestor_dialog_handle(titlebar)
                if dlg:
                    logger.info("检测到嵌套 DTS 文件对话框 0x%X title=%r",
                                dlg, titles)
                    return dlg
            except Exception:
                continue
        return 0

    def _control_titles(self, ctrl) -> list:
        titles = []
        for getter in (
            lambda: ctrl.legacy_properties().get("Value", ""),
            ctrl.window_text,
        ):
            try:
                title = getter()
                if title:
                    titles.append(title)
            except Exception:
                pass
        return list(dict.fromkeys(titles))

    def _ancestor_dialog_handle(self, ctrl) -> int:
        """从 TitleBar 向上找 class=#32770 或 control_type=Dialog 的祖先。"""
        cur = ctrl
        for _ in range(8):
            try:
                cur = cur.parent()
                info = cur.element_info
                cls = getattr(info, "class_name", "") or ""
                ctype = getattr(info, "control_type", "") or ""
                if cls == "#32770" or ctype == "Dialog":
                    return int(cur.handle)
            except Exception:
                break
        return 0

    def _dialog_titles(self, hwnd: int, element=None) -> list:
        """收集 #32770 对话框标题：顶层 name/window text + 子 TitleBar.Value。"""
        titles = []
        try:
            name = getattr(element, "name", "") if element is not None else ""
            if name:
                titles.append(name)
        except Exception:
            pass
        try:
            title = bg.window_title(hwnd)
            if title:
                titles.append(title)
        except Exception:
            pass
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd)
            titlebar = root.child_window(auto_id="TitleBar", found_index=0)
            if titlebar.exists(timeout=0.2):
                titles.extend(self._control_titles(titlebar))
        except Exception:
            pass
        return list(dict.fromkeys(titles))

    def _dialog_first_edit_handle(self, hwnd: int) -> int:
        """取文件对话框内第一个 Edit 句柄；失败则返回 0。"""
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd)
            edit = root.child_window(control_type="Edit", found_index=0)
            if edit.exists(timeout=0.5):
                return int(edit.handle)
        except Exception:
            pass
        return 0

    def _dialog_button(self, hwnd: int, titles: list):
        """在指定对话框子树内按按钮标题查找控件。"""
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd)
            for title in titles:
                btn = root.child_window(title=title, control_type="Button", found_index=0)
                if btn.exists(timeout=0.3):
                    return btn
            for btn in root.descendants(control_type="Button"):
                try:
                    name = (btn.window_text() or "").strip()
                    if any(title in name for title in titles):
                        return btn
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _click_dialog_button(self, hwnd: int, titles: list, tag: str) -> bool:
        btn = self._dialog_button(hwnd, titles)
        if not btn:
            return False
        logger.info("%s: 点击按钮 %s", tag, titles)
        return self.click_ctrl(btn)

    def _wait_dialog_gone(self, dlg: int, wait: float = 6) -> bool:
        """等弹窗销毁或前台离开它（回车关闭后）；返回是否已关闭/离开。"""
        if not dlg:
            return True
        deadline = time.time() + wait
        while time.time() < deadline:
            if not bg.window_exists(dlg):
                return True
            fg = bg.active_window()
            if fg and fg != dlg:
                return True
            time.sleep(0.3)
        return False

    def confirm_enter_if_dialog(self, wait: float = 2.5, max_times: int = 3,
                                exclude=None) -> bool:
        """文件对话框提交后：若又出现 DTS #32770 弹窗（覆盖/确认）则确认。

        旧代码在主窗口 self.window 里搜按钮 title="是(Y)" —— 覆盖确认是独立顶层
        弹窗，主窗子树里永远没有，导致 8 轮空等后只能盲打 {ENTER}{ENTER}（状态
        失步的根源之一）。这里改为看前台/枚举弹窗：出现 #32770 时优先点击
        "是(Y)"/"确定"，失败再回车兜底；最多 max_times 个连续弹窗。
        """
        handled = False
        exclude = set(exclude or [])
        for _ in range(max_times):
            dlg = self.wait_fg_dialog(wait=wait, exclude=exclude)
            if not dlg:
                break
            handled = True
            logger.info("检测到确认/覆盖弹窗 0x%X (class=%s title=%r) → 确认",
                        dlg, bg.window_class(dlg), bg.window_title(dlg))
            if not self._click_dialog_button(dlg, ["是(Y)", "是", "确定"], "确认/覆盖弹窗"):
                bg.send_keys(dlg, "{ENTER}")
            self._wait_dialog_gone(dlg, wait=4)
            exclude.add(dlg)
        return handled

    def drive_file_dialog(self, file_name: str, mode: str = "save",
                          timeout: float = 12) -> bool:
        """驱动「保存列表/载入列表」文件对话框（点击按钮打开弹窗后调用）。

        全程只作用于 DTS 文件对话框，不再切焦点到主窗口或强找 Edit：
          1. 按 DTS 进程 + 标题等待「保存列表/载入列表」顶层弹窗
          2. 优先直接设置 Edit 文本，再点击 保存(S)/打开(O)
          3. 覆盖/确认 #32770 若出现 → 点击 是(Y)/确定
          4. 等文件对话框真正关闭再返回（避免后续按键打向正在关闭的弹窗）

        mode: "save" 保存列表 / "load" 载入列表（仅用于日志文案）。
        """
        tag = "保存" if mode == "save" else "载入"
        title_keywords = ["保存列表"] if mode == "save" else ["载入列表"]
        dlg = self.wait_dts_dialog_by_title(title_keywords, wait=timeout)
        if not dlg:
            logger.warning("%s文件对话框未出现 —— 跳过输入", tag)
            return False
        logger.info("%s文件对话框输入文件名 %s 并回车", tag, file_name)
        edit = self._dialog_first_edit_handle(dlg)
        if edit:
            logger.info("%s文件对话框使用 Edit 0x%X 接收文件名", tag, edit)
            bg.set_text(edit, file_name)
        else:
            # 兜底：系统文件框通常默认选中文件名输入框，直接键入即可。
            bg.send_keys(dlg, file_name)
        action_titles = ["保存(S)", "保存"] if mode == "save" else ["打开(O)", "打开"]
        if not self._click_dialog_button(dlg, action_titles, f"{tag}文件对话框"):
            logger.warning("%s文件对话框未找到操作按钮，回退 Enter", tag)
            bg.send_keys(dlg, "{ENTER}", target_hwnd=edit or None)
        # 覆盖/确认（是否出现不确定：出现才回车默认按钮）
        self.confirm_enter_if_dialog(wait=2.5, max_times=3, exclude={dlg})
        # 等文件对话框真正关闭
        self._wait_dialog_gone(dlg, wait=8)
        return True

    def _focus_list(self):
        """
        聚焦列表窗格(auto_id=1131)，让 DOWN/UP 能切换选中行

        列表窗格信息:
          auto_id="1131", class=AfxWnd80su, {l:20 t:108 r:1903 b:937}

        后台从不激活 → 控件无键盘焦点，方向键无效；先激活窗口再聚焦列表。
        返回窗格控件，供 send_keys_to 做原子「聚焦+投递」；失败返回 None。
        """
        # 后台从不激活 → 控件无键盘焦点，方向键无效；先激活窗口再聚焦列表
        self.focus_active_window()
        try:
            pane = self.window.child_window(
                auto_id="1131", control_type="Pane", found_index=0
            )
            if pane.exists(timeout=2):
                self.set_focus_bg(pane)  # 后台=消息式设焦点，不抢前台
                time.sleep(0.5)
                logger.info("已聚焦列表窗格")
                return pane
        except Exception as e:
            logger.warning(f"聚焦列表失败: {e}")

        # 降级: 点击窗格第一行位置（窗口已激活，SendMessage 点击才能拿到焦点）
        try:
            pane = self.window.child_window(
                auto_id="1131", control_type="Pane", found_index=0
            )
            if pane.exists(timeout=1):
                r = pane.rectangle()
                self.click_at(r.left + 50, r.top + 30)
                time.sleep(0.5)
                logger.info("已点击列表聚焦(降级)")
                return pane
        except Exception as e:
            logger.warning(f"点击列表失败: {e}")
        return None

    def copy_all_rows(self, copy_btn_id: str, max_rows: int = 20) -> list:
        """
        逐行选中 → 点击复制 → 对比剪贴板，内容重复则停止

        Args:
            copy_btn_id: 复制按钮的 auto_id
            max_rows: 最大复制行数（防止死循环）

        Returns:
            所有复制到的内容列表
        """
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()

        results = []
        last_text = None

        pane = self._focus_list()
        for _ in range(3):
            # send_keys_to: 同一 AttachThreadInput 块内 SetFocus(窗格)+投递，
            # 前台守卫即使随后抢走前台也不打断本次方向键
            self.send_keys_to("{UP}", pane)
            time.sleep(1)

        for i in range(max_rows):
            if i > 0:
                logger.info("选择下一个选项")
                # 先点列表聚焦，再 DOWN（原子聚焦+投递）
                pane = self._focus_list()
                self.send_keys_to("{DOWN}", pane)
                time.sleep(2)
            # 点击复制按钮
            btn = self.window.child_window(
                auto_id=copy_btn_id, control_type="Button", found_index=0
            )
            if not btn.exists(timeout=2):
                logger.warning(f"复制按钮 (auto_id={copy_btn_id}) 不存在")
                break
            logger.info("点击 复制按钮")
            self.click_ctrl(btn)
            time.sleep(1)

            # 复制成功提示
            ok = self.window.child_window(
                auto_id="2", control_type="Button", found_index=0
            )
            logger.info("点击 确认")
            self.click_ctrl(ok)
            time.sleep(0.5)

            # 读剪贴板
            try:
                text = root.clipboard_get()
            except Exception:
                text = ""

            text = text.strip()
            logger.info("粘贴板内容：")
            logger.info(text)

            # if not text:
            #     logger.info(f"  第{i+1}行: 空，停止")
            #     break
            # 内容与上次重复 → 已到末尾，结束
            if last_text is not None and text == last_text:
                logger.info(f"  第{i+1}行: 内容重复，复制完成")
                break

            results.append(text)
            last_text = text
            logger.info(f"  第{i+1}行: {text[:60]}...")
            time.sleep(0.5)

        root.destroy()
        logger.info(f"  共复制 {len(results)} 行")
        return results

    # ═══════════════════════════════════════════════
    #  自绘按钮定位（跨分辨率，相对比例）
    # ═══════════════════════════════════════════════

    def _control_exists(self, auto_id: str, control_type: str = "Button",
                        timeout: float = 1) -> bool:
        try:
            ctrl = self.window.child_window(
                auto_id=auto_id, control_type=control_type, found_index=0
            )
            return bool(ctrl.exists(timeout=timeout))
        except Exception:
            return False

    def _click_until_control(self, name: str, click, verify_auto_id: str,
                             verify_control_type: str = "Button",
                             attempts: int = 3,
                             verify_timeout: float = 5) -> bool:
        """点击自绘区域后用目标控件验证页面跳转，未跳转则重连并重试。"""
        if self._control_exists(verify_auto_id, verify_control_type, timeout=0.5):
            logger.info("%s: 目标控件 %s 已存在，跳过点击", name, verify_auto_id)
            return True
        for i in range(attempts):
            if i > 0:
                logger.warning("%s: 点击后未进入目标页面，重连后重试 %d/%d",
                               name, i + 1, attempts)
                self._reconnect_main(timeout=5)
            if not click():
                continue
            if self._control_exists(
                    verify_auto_id, verify_control_type, timeout=verify_timeout):
                logger.info("%s: 点击生效，目标控件 %s 已出现", name, verify_auto_id)
                return True
        logger.warning("%s: 连续 %d 次点击后目标控件 %s 仍未出现",
                       name, attempts, verify_auto_id)
        return False

    # ── 文本锚点 ──────────────────────────────────

    def _click_below_text(self, auto_id: str, rx: float, ry: float) -> bool:
        """
        以文本控件为锚点，按比例偏移点击

        Args:
            auto_id: 锚点文本控件的 AutomationId
            rx: 水平偏移 = 目标X到文本左边缘 / 文本宽度
            ry: 垂直偏移 = 目标Y到文本底部 / 文本高度
        """
        try:
            text = self.window.child_window(
                auto_id=auto_id, control_type="Text", found_index=0
            )
            if text.exists(timeout=3):
                r = text.rectangle()
                target_x = r.left + int(r.width() * rx)
                target_y = r.bottom + int(r.height() * ry)
                self.click_at(target_x, target_y)
                logger.info(f"✓ 点击文本锚点 ({target_x},{target_y})")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"文本锚点失败: {e}")
        return False

    # ── 底部按钮锚点 ──────────────────────────────

    def _click_image_btn(self, rx: float, ry: float) -> bool:
        """
        以"上翻页"按钮 (auto_id=1013) 为锚点，按比例偏移点击

        Args:
            rx: 水平偏移 = 目标X到按钮左边缘 / 按钮宽度
            ry: 垂直偏移 = 目标Y / 内容区高度
        """
        try:
            btn = self.window.child_window(auto_id="1013", control_type="Button")
            if btn.exists(timeout=3):
                r = btn.rectangle()
                wr = self.window.rectangle()
                content_top = wr.top
                content_bottom = r.top
                target_x = r.left + int(r.width() * rx)
                target_y = content_top + int((content_bottom - content_top) * ry)
                self.click_at(target_x, target_y)
                logger.info(f"✓ 点击按钮锚点 ({target_x},{target_y})")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"按钮锚点失败: {e}")
        return False

    # ═══════════════════════════════════════════════
    #  窗口连接
    # ═══════════════════════════════════════════════

    def _reconnect_main(self, timeout: int = 15) -> bool:
        """重连 DTS 主窗口；超时打诊断（期间见过的顶层窗口+pid），便于定位启动失败

        匹配顺序：
          1. 类名快速路径（CDTS650MainClass 主窗 / #32770 弹窗）
          2. 跨版本兜底：按 DTS 进程匹配任意顶层窗口 —— 类名随版本漂移
             （如 DTS 20260706 的主窗类已不是 CDTS650MainClass）时仍能连上。
        """
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline:
            wins = find_elements(backend="uia", top_level_only=True)
            for w in wins:
                try:
                    if w.class_name == "CDTS650MainClass":
                        self._connect_by_handle(w.handle, w.process_id)
                        self._apply_window_hiding()
                        logger.info("已连接 DTS 主窗口 (hwnd=%s)", w.handle)
                        return True
                except Exception:
                    continue
            for w in wins:
                try:
                    if w.class_name == "#32770" and "DTS" in (w.name or ""):
                        self._connect_by_handle(w.handle, w.process_id)
                        self._apply_window_hiding()
                        logger.info("已连接 DTS 弹窗 (hwnd=%s)", w.handle)
                        return True
                except Exception:
                    continue
            # 跨版本兜底：DTS 进程的任意顶层窗口（类名不再可靠）
            for w in self._find_windows_by_exe():
                try:
                    self._connect_by_handle(w.handle, w.process_id)
                    self._apply_window_hiding()
                    logger.info("已连接 DTS 进程窗口 (hwnd=%s, class=%s)",
                                w.handle, w.class_name)
                    return True
                except Exception:
                    continue
            for w in wins:
                try:
                    seen.add(f"{w.class_name}|{w.name}|pid={w.process_id}")
                except Exception:
                    pass
            time.sleep(0.5)
        pid = self._find_process()
        if pid:
            logger.warning(
                "DTS 主窗口未在 %ds 内出现；期间见过的顶层窗口: %s；"
                "（DTS 进程仍在运行 PID=%s → 是窗口/类名匹配问题，进程没死）",
                timeout, sorted(seen)[:20] or "（无）", pid)
        else:
            logger.warning(
                "DTS 主窗口未在 %ds 内出现；期间见过的顶层窗口: %s；"
                "（DTS 进程已退出 —— 自动化不杀进程，疑似导航误触或 DTS 自身退出）",
                timeout, sorted(seen)[:20] or "（无）")
        return False

    def _wait_for_dts_window(self, timeout: int = 30):
        """等 DTS 启动确认弹窗 (#32770 + 子控件"确认")；超时打所见窗口诊断"""
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline:
            wins = find_elements(backend="uia", top_level_only=True)
            for w in wins:
                try:
                    if w.class_name == "#32770":
                        for child in w.children():
                            if child.name == "确认":
                                self._connect_by_handle(w.handle)
                                self._apply_window_hiding()
                                logger.info("已连接 DTS 确认窗口 (hwnd=%s)", w.handle)
                                return True
                except Exception:
                    continue
            for w in wins:
                try:
                    seen.add(f"{w.class_name}|{w.name}")
                except Exception:
                    pass
            time.sleep(0.5)
        logger.warning("DTS 确认窗口未在 %ds 内出现；期间见过的顶层窗口: %s",
                       timeout, sorted(seen)[:20] or "（无）")
        return False

    def ensure_running(self, timeout: int = 30) -> bool:
        if self.connect_existing():
            self._apply_window_hiding()
            return True
        logger.info(f"启动 DTS: {self.APP_EXE}")
        if self.background and self.elevated:
            task = bg.launch_elevated(self.APP_EXE)
            if task is None:
                logger.warning("计划任务提权启动失败，回退普通启动")
                bg.launch(self.APP_EXE, minimized=self.start_minimized)
        elif self.background:
            bg.launch(self.APP_EXE, minimized=self.start_minimized)
        else:
            import subprocess

            subprocess.Popen([self.APP_EXE])
        self._launched_by_us = True
        logger.info("等待 DTS 启动窗口 (超时 %ds)", timeout)
        ok = self._wait_for_dts_window(timeout)
        logger.info("DTS 启动窗口连接: %s", "成功" if ok else "失败")
        return ok
