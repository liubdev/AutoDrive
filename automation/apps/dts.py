"""
DTS 应用自动化模块
"""

import time
import logging
import subprocess
from pathlib import Path
from typing import Optional

from pywinauto import Application
from pywinauto.findwindows import find_elements

from . import BaseApp

logger = logging.getLogger("autocar.apps.dts")


class DtsApp(BaseApp):
    APP_EXE = r"C:\Program Files (x86)\DTS\DTS20220525\DTS650.exe"
    INSTANCE_MULTI = False

    # ── 点击"确认"按钮（第一步） ────────────────────

    def confirm(self, timeout: int = 30) -> bool:
        """
        点击启动后的"确认"按钮

        DTS 启动后显示 splash 页 + 确认对话框。
        点击"确认"后对话框关闭，进入主界面。

        Returns:
            True 如果已点击"确认"
        """
        if not self.window:
            # 如果还没连接，等窗口出现
            logger.info("等待 DTS 窗口...")
            if not self._wait_for_dts_window(timeout):
                return False

        logger.info("查找'确认'按钮...")

        # 策略 A: 在窗口内按文字查找
        try:
            btn = self.window.child_window(title="确认", control_type="Button")
            if btn.exists(timeout=5):
                btn.click()
                logger.info("✓ 已点击'确认'按钮 (策略A: title)")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"策略A失败: {e}")

        # 策略 B: 按 auto_id="1" 查找
        try:
            btn = self.window.child_window(auto_id="1", control_type="Button")
            if btn.exists(timeout=3):
                btn.click()
                logger.info("✓ 已点击'确认'按钮 (策略B: auto_id=1)")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"策略B失败: {e}")

        # 策略 C: 遍历所有 Button 找文字包含"确认"的
        try:
            buttons = self.window.descendants(control_type="Button")
            for btn in buttons:
                try:
                    txt = btn.window_text()
                    if "确认" in txt or "确定" in txt:
                        btn.click()
                        logger.info(f"✓ 已点击'{txt}'按钮 (策略C)")
                        time.sleep(2)
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"策略C失败: {e}")

        logger.error("所有策略均无法找到'确认'按钮")
        return False

    # ── 窗口定位（页面在同一窗口内切换，不用重连） ────────

    def _ensure_window(self, timeout: int = 10) -> bool:
        """
        确保当前窗口有效。
        页面在同一窗口内切换，不关闭窗口，所以不需要重新连接。
        如果 `self.window` 不可用，按已知标题" DTS服务电话"重新查找。
        """
        if self.window:
            try:
                self.window.exists()
                return True
            except Exception:
                pass
        # 按已知对话框标题重新找
        deadline = time.time() + timeout
        while time.time() < deadline:
            wins = find_elements(backend="uia", top_level_only=True)
            for w in wins:
                try:
                    if w.class_name == "#32770" and "DTS" in (w.name or ""):
                        return self._connect_by_handle(w.handle, w.process_id)
                except Exception:
                    continue
            time.sleep(0.5)
        return False

    def one_click_enter(self, timeout: int = 30) -> bool:
        """
        点击进入系统的按钮（自绘图片，不在 UIA 树中）

        最稳健方案：以底部导航栏"上翻页"按钮为锚点推算位置。
        底部按钮是真正的 UIA 控件（有 auto_id="1013"），任何分辨率都能定位。
        "一键进入"在内容区左上角，跟上翻页左边缘对齐。
        """
        if not self._ensure_window(timeout):
            return False

        logger.info("查找进入按钮...")

        # ── 策略 A: 以底部"上翻页"按钮为锚点（最稳健） ──
        #   底部按钮 Y=955，内容区高度 = 955
        #   "一键进入" y=170 → 内容区 170/955 = 17.8%
        #   "一键进入" x=123 → 跟上翻页左边缘 (x=21) 对齐
        logger.info("策略A: 以'上翻页'按钮为锚点...")
        try:
            # 找底部"上翻页"按钮（auto_id="1013"，一定有）
            page_up = self.window.child_window(
                auto_id="1013", control_type="Button"
            )
            if page_up.exists(timeout=2):
                r = page_up.rectangle
                # "一键进入"左边缘与"上翻页"左边缘对齐
                target_x = r.left + 102  # 左边缘往右偏移 102px (123-21)
                # "一键进入"在内容区 17.8% 位置
                # 内容区底部 = 上翻页按钮的顶部
                content_bottom = r.top
                target_y = int(content_bottom * 0.178)

                from pywinauto import mouse
                mouse.click(coords=(target_x, target_y))
                logger.info(f"✓ 已点击 (策略A: 锚点推算) ({target_x},{target_y})")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"策略A失败: {e}")

        # ── 策略 B: 窗口相对坐标 ──
        logger.info("策略B: 窗口相对坐标...")
        try:
            from vision.locate import ResolutionAdapter
            adapter = ResolutionAdapter()
            win_handle = self._window.handle if self._window else None
            if win_handle:
                sx, sy = adapter.screen_from_relative(win_handle, 0.064, 0.162)
                from pywinauto import mouse
                mouse.click(coords=(sx, sy))
                logger.info(f"✓ 已点击 (策略B: 相对坐标) ({sx},{sy})")
                time.sleep(2)
                return True
        except Exception:
            logger.warning("策略B失败")

        # ── 策略 C: OCR ──
        logger.info("策略C: OCR...")
        try:
            if self.click_text("一键", timeout=3):
                logger.info("✓ 已点击 (策略C: OCR)")
                time.sleep(2)
                return True
        except Exception:
            logger.warning("策略C失败")

        logger.error("所有策略均无法找到进入按钮")
        return False

    def diagnose_engine_system(self, timeout: int = 30) -> bool:
        """发动机系统诊断 —— 选项默认已选中，直接 Enter"""
        if not self._ensure_window(timeout):
            return False
        logger.info("发动机系统诊断: 发送 Enter")
        self.send_enter()
        time.sleep(2)
        return True

    # ── 窗口匹配 ──────────────────────────────────────

    def _wait_for_dts_window(self, timeout: int = 30):
        """
        等待 DTS 窗口出现

        DTS 的窗口特征是:
          - class_name = "#32770" (标准对话框类)
          - 包含 splash 页面和"确认"按钮
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # 按类名找 DTS 主窗口
                wins = find_elements(backend="uia", top_level_only=True)
                for w in wins:
                    try:
                        if w.class_name == "#32770":
                            # 验证：检查是否包含"确认"按钮
                            for child in w.children():
                                try:
                                    if child.name == "确认":
                                        return self._connect_by_handle(w.handle)
                                except Exception:
                                    continue
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _find_window_by_pid(self, pid: int):
        """DTS 窗口是 #32770 对话框类"""
        wins = find_elements(backend="uia", top_level_only=True)
        for w in wins:
            try:
                if w.process_id == pid and w.class_name == "#32770":
                    return w
            except Exception:
                continue
        return None

    # ── 基类覆盖：DTS 的启动方式 ────────────────────

    def ensure_running(self, timeout: int = 30) -> bool:
        """
        启动 DTS 并等待确认对话框出现

        DTS 的启动流程:
          1. 启动 DTS650.exe
          2. 显示 splash 页 + "确认"按钮
        """
        # 尝试连已有实例
        if self.connect_existing():
            return True

        # 启动 DTS
        logger.info(f"启动 DTS: {self.APP_EXE}")
        proc = subprocess.Popen([self.APP_EXE])
        self._launched_by_us = True

        # 等待窗口
        return self._wait_for_dts_window(timeout)
