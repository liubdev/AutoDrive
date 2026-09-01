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

    def __init__(self):
        super().__init__()
        # DTS650 路径唯一来源：settings.dts_exe（默认值定义在 config/settings.py，
        # 首次运行自动生成 data/config.json 模板，可在其中覆盖）
        self.APP_EXE = settings.dts_exe
        self.background = getattr(settings, "dts_background", True)
        self.window_mode = getattr(settings, "dts_window_mode", "offscreen")
        self.start_minimized = getattr(settings, "dts_start_minimized", True)
        self.elevated = getattr(settings, "dts_elevated", False)

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
        return self._click_image_btn(rx=0.573, ry=0.178)

    # ── 点击进入系统 ──
    # 锚点: "当前设置:车下使用" 文本 (auto_id=1185)  宽1880 高38
    # 目标: (145,152) → rx=(145-20)/1880=0.066, ry=(152-89)/38=1.66

    def enter_system(self, timeout: int = 30) -> bool:
        if not self._reconnect_main(timeout):
            return False
        return self._click_below_text(auto_id="1185", rx=0.066, ry=1.66)

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
        return None

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

    def _dts_top_windows(self) -> list:
        """当前 DTS 进程的全部顶层窗口句柄（主窗+弹窗），新的优先。"""
        handles = set()
        try:
            for w in self._find_windows_by_exe():
                handles.add(int(w.handle))
        except Exception:
            pass
        if not handles:
            hwnd = self._hwnd()
            if hwnd:
                handles.add(hwnd)
        return sorted(handles, reverse=True)

    def focus_active_window(self, timeout: int = 8) -> bool:
        """聚焦 DTS 当前窗口（主窗或弹窗）—— 后台模式也执行。

        后台模式 DTS 常驻后台、从不激活：弹窗（保存/载入/确认）打开后系统不会
        给其输入框分配键盘焦点，PostMessage 按键会投到主窗口/旧焦点上而无效。
        本方法把 DTS 进程的顶层窗口依次置为活动（AttachThreadInput +
        SetForegroundWindow；AutoDrive 是 topmost，视觉上 DTS 仍被盖住），
        弹窗被激活后系统才会给其默认输入框分配焦点，后续按键落到正确控件上。
        """
        if not self.background:
            return bool(self.window and self.window.set_focus())
        for hwnd in self._dts_top_windows():
            if bg.force_foreground(hwnd):
                time.sleep(0.15)
                return True
        return False

    def focus_edit_in_dialog(self, timeout: int = 5) -> bool:
        """等弹窗（保存/载入）的文件名输入框出现并聚焦。

        先激活 DTS 窗口，再找到当前可见的 Edit 并线程级 SetFocus —— 之后
        send_keys 的文件名才会落到输入框，而不是打进主窗口空处。
        """
        self.focus_active_window()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                edit = self.window.child_window(
                    control_type="Edit", found_index=0)
                if edit.exists(timeout=0.5):
                    r = edit.rectangle()
                    if r.width() > 0 and r.height() > 0:   # 可见
                        if self.set_focus_bg(edit):
                            time.sleep(0.3)
                            logger.info("已聚焦文件名输入框")
                            return True
            except Exception:
                pass
            time.sleep(0.3)
        logger.warning("弹窗文件名输入框未在 %ds 内出现/聚焦", timeout)
        return False

    def _focus_list(self):
        """
        聚焦列表窗格(auto_id=1131)，让 DOWN/UP 能切换选中行

        列表窗格信息:
          auto_id="1131", class=AfxWnd80su, {l:20 t:108 r:1903 b:937}
        """
        # 后台从不激活 → 控件无键盘焦点，方向键无效；先激活窗口再聚焦列表
        self.focus_active_window()
        try:
            pane = self.window.child_window(
                auto_id="1131", control_type="Pane", found_index=0
            )
            if pane.exists(timeout=2):
                self.set_focus_bg(pane)  # 后台=消息式设焦点，不抢前台
                time.sleep(0.3)
                logger.info("已聚焦列表窗格")
                return True
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
                return True
        except Exception as e:
            logger.warning(f"点击列表失败: {e}")
        return False

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

        self._focus_list()
        for _ in range(3):
            self.send_keys("{UP}")
            time.sleep(1)

        for i in range(max_rows):
            if i > 0:
                logger.info("选择下一个选项")
                # 先点列表聚焦，再 DOWN
                self._focus_list()
                self.send_keys("{DOWN}")
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
            ry: 垂直偏移 = 目标Y / 内容区底部Y
        """
        try:
            btn = self.window.child_window(auto_id="1013", control_type="Button")
            if btn.exists(timeout=3):
                r = btn.rectangle()
                target_x = r.left + int(r.width() * rx)
                target_y = int(r.top * ry)
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
