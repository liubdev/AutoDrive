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

    def one_click_enter(self, timeout: int = 30) -> bool:
        """
        点击进入系统的按钮(自绘图片按钮，UIA 显示为无名称 "" Button)
        多策略自动降级:
          A. OCR 找"点击进入系统"文字
          B. 通过"车下使用"按钮位置推算下方按钮
          C. 全窗口遍历找第二个无名称 "" Button
        """
        if not self.window:
            logger.info("等待 DTS 窗口...")
            if not self._wait_for_dts_window(timeout):
                return False

        logger.info("查找进入按钮...")

        # ── 策略 A: OCR 定位 ──
        logger.info("策略A: OCR 文字定位...")
        try:
            if self.click_text("点击进入系统", timeout=3):
                logger.info("✓ 已点击 (策略A: OCR)")
                time.sleep(2)
                return True
        except Exception:
            logger.warning("策略A失败")

        # ── 策略 B: 通过"车下使用"按钮位置推算下方 ──
        logger.info("策略B: 通过'车下使用'位置推算下方按钮...")
        try:
            for title_text in ("车下使用", "当前设置"):
                sibling = self.window.child_window(
                    title=title_text, control_type="Button"
                )
                if sibling.exists(timeout=1):
                    r = sibling.rectangle
                    # 按钮在"车下使用"下方 -> 取下方居中位置
                    target_x = r.left + r.width() // 2
                    target_y = r.bottom + 20  # 下方偏移
                    from pywinauto import mouse

                    mouse.click(coords=(target_x, target_y))
                    logger.info(f"✓ 已点击 (策略B: 下方推算) ({target_x},{target_y})")
                    time.sleep(2)
                    return True
        except Exception:
            logger.warning("策略B失败")

        # ── 策略 C: 遍历所有按钮，找"车下使用"后面的无名称按钮 ──
        logger.info("策略C: 遍历查找无名称按钮...")
        try:
            buttons = self.window.descendants(control_type="Button")
            # 先找到"车下使用"的索引
            found_car = False
            for btn in buttons:
                try:
                    txt = btn.window_text()
                    if "车下使用" in txt:
                        found_car = True
                        continue
                    if found_car:
                        # "车下使用"之后的下一个按钮就是目标
                        btn.click()
                        logger.info("✓ 已点击 (策略C: 顺序遍历)")
                        time.sleep(2)
                        return True
                except Exception:
                    continue
        except Exception:
            logger.warning("策略C失败")

        logger.error("所有策略均无法找到进入按钮")
        return False

    def diagnose_engine_system(self, timeout: int = 30) -> bool:
        """
        发动机系统诊断
        """
        if not self.window:
            logger.info("等待 DTS 窗口...")
            if not self._wait_for_dts_window(timeout):
                return False

        # logger.info("查找'发动机系统诊断'按钮...")

        # # 策略 A: OCR 双击
        # logger.info("策略A: OCR 双击定位...")
        # try:
        #     if self.double_click_text("发动机系统诊断", timeout=3):
        #         logger.info("✓ 已双击 (策略A: OCR)")
        #         time.sleep(2)
        #         return True
        # except Exception:
        #     logger.warning("策略A失败")

        # # 策略 B: 图片模板匹配双击
        # logger.info("策略B: 图片模板匹配双击...")
        # try:
        #     if self.double_click_image("dts_engine_diag.png", threshold=0.7, timeout=3):
        #         logger.info("✓ 已双击 (策略B: 图片)")
        #         time.sleep(2)
        #         return True
        # except Exception:
        #     logger.warning("策略B失败")

        # logger.error("无法找到'发动机系统诊断'按钮")
        # return False

        # 选项默认选中 发送Enter指令
        logger.info("选项默认选中 发送Enter指令 '发动机系统诊断'选项")
        self.send_enter()

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
