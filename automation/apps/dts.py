"""
DTS 应用自动化模块
"""

import time
import logging
import subprocess
from pathlib import Path
from typing import Optional
from pywinauto.findwindows import find_elements

from . import BaseApp
from config import settings

logger = logging.getLogger("autocar.apps.dts")


class DtsApp(BaseApp):
    APP_EXE = r"C:\Program Files (x86)\DTS\DTS20220525\DTS650.exe"
    INSTANCE_MULTI = False

    # ── 点击"确认"按钮（第一步） ────────────────────

    def confirm(self, timeout: int = 30) -> bool:
        """
        DTS 启动后显示 splash 页。
        点击"确认"，进入主界面。
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

    # ── 重新连接（关键：确认对话框关闭后需连到主窗口） ─────

    def _reconnect_main(self, timeout: int = 15) -> bool:
        """
        点击"确认"后旧对话框关闭，重连到 DTS650 主窗口

        新窗口特征:
          - 类名: CDTS650MainClass  (主窗口)
          - 或:   #32770            (内容面板，标题含 "DTS服务电话")
          - 包含底部按钮: 上翻页 (auto_id=1013)
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                wins = find_elements(backend="uia", top_level_only=True)
                for w in wins:
                    try:
                        if w.class_name == "CDTS650MainClass":
                            logger.info(f"找到主窗口 DTS650 (handle={w.handle})")
                            return self._connect_by_handle(w.handle, w.process_id)
                    except Exception:
                        continue

                for w in wins:
                    try:
                        if w.class_name == "#32770" and "DTS" in (w.name or ""):
                            logger.info(f"找到 DTS 对话框 (handle={w.handle})")
                            return self._connect_by_handle(w.handle, w.process_id)
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.5)

        logger.warning("重连 DTS 主窗口超时")
        return False

    def one_click_enter(self, timeout: int = 30) -> bool:
        """
        点击"一键进入"按钮（自绘图片，位置 123,170）
        以"上翻页"为锚点推算，跨分辨率自适应。
        """
        if not self._reconnect_main(timeout):
            return False
        logger.info("以'上翻页'按钮为锚点，推算'一键进入'...")
        if self._click_image_btn(offset_x=102, ratio_y=0.178):
            return True
        # 降级：窗口相对坐标
        logger.info("降级: 窗口相对坐标...")
        try:
            from vision.locate import ResolutionAdapter

            adapter = ResolutionAdapter()
            sx, sy = adapter.screen_from_relative(self._window.handle, 0.064, 0.162)
            from pywinauto import mouse

            mouse.click(coords=(sx, sy))
            logger.info(f"✓ 已点击 ({sx},{sy})")
            time.sleep(2)
            return True
        except Exception:
            pass
        return False

    def enter_system(self, timeout: int = 30) -> bool:
        """点击"点击进入系统"按钮（自绘图片）"""
        if not self._reconnect_main(timeout):
            return False
        return self._click_below_text(auto_id="1185", offset_x=125, offset_y=65)

    def save_info_to_txt(self, output: str = None) -> Optional[str]:
        """
        保存弹窗中的诊断信息到 txt 文件

        从 auto_id="1202" 的文本控件读取 VIN/ECU 等信息。

        Args:
            output: 保存路径，默认 data/reports/dtc_xxx.txt

        Returns:
            文件路径，失败返回 None
        """
        try:
            edit = self.window.child_window(
                auto_id="1202", control_type="Edit", found_index=0
            )
            if not edit.exists(timeout=3):
                logger.warning("未找到诊断信息控件 (auto_id=1202)")
                return None

            text = edit.window_text()
            if not text.strip():
                text = edit.element_info.value  # 兜底用 ValuePattern

            if output is None:
                from datetime import datetime

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                output = str(settings.reports_dir / f"dtc_{ts}.txt")

            with open(output, "w", encoding="utf-8") as f:
                f.write(text)

            logger.info(f"诊断信息已保存: {output}")
            return output
        except Exception as e:
            logger.error(f"保存诊断信息失败: {e}")
            return None

    # ── 通用：在指定文本控件下方点击 ─────────────────

    def _click_below_text(self, auto_id: str, offset_x: int, offset_y: int) -> bool:
        """
        找到文本控件，在其下方偏移位置点击

        Args:
            auto_id: 文本控件的 AutomationId
            offset_x: 距文本左边缘的 X 偏移
            offset_y: 距文本底部的 Y 偏移
        """
        try:
            text = self.window.child_window(
                auto_id=auto_id, control_type="Text", found_index=0
            )
            if text.exists(timeout=3):
                r = text.rectangle()
                target_x = r.left + offset_x
                target_y = r.bottom + offset_y
                from pywinauto import mouse

                mouse.click(coords=(target_x, target_y))
                logger.info(f"✓ 已点击 ({target_x},{target_y}) [在 {auto_id} 下方]")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"文本锚点点击失败: {e}")
        return False

    # ── 通用图片按钮点击（以"上翻页"为锚点） ──────────

    def _click_image_btn(self, offset_x: int, ratio_y: float) -> bool:
        """
        以底部"上翻页"按钮(auto_id="1013")为锚点推算位置
        """
        try:
            page_up = self.window.child_window(auto_id="1013", control_type="Button")
            if page_up.exists(timeout=3):
                r = page_up.rectangle()
                target_x = r.left + offset_x
                target_y = int(r.top * ratio_y)
                from pywinauto import mouse

                mouse.click(coords=(target_x, target_y))
                logger.info(f"✓ 已点击图片按钮 ({target_x},{target_y})")
                time.sleep(2)
                return True
        except Exception as e:
            logger.warning(f"图片按钮点击失败: {e}")
        return False

    # ── 窗口匹配 ──────────────────────────────────────

    def _wait_for_dts_window(self, timeout: int = 30):
        """
        等待 DTS 窗口出现
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # 按类名找 DTS 主窗口
                wins = find_elements(backend="uia", top_level_only=True)
                for w in wins:
                    try:
                        if w.class_name == "#32770":
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
