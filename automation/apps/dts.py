"""
DTS 应用自动化模块

控件结构 (从 ui_tree_20260720_150215.json 解析):
  DTS650.exe 启动后:
    ┌─ Pane (#32770)  ← DTS 主窗口
    │  ├─ Button "确认" (auto_id="1")
    │  └─ Pane (Shell Embedding)
    │     └─ splash.html (IE 控件加载的启动页)
    │
    点击"确认"后 → 页面变化，进入下一个界面

  app.disconnect()
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
    # ── 改成你的 DTS 实际路径 ──
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
                time.sleep(2)  # 等待页面变化
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
