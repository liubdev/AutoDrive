"""
DTS 应用自动化模块

自绘按钮定位策略（跨分辨率自适应）:
  A. UIA 文字查找 → 最稳（标准控件）
  B. 图片模板匹配 → 无文字图片按钮
  C. 锚点相对比例 → 自绘按钮（非像素偏移）

锚点控件信息:
  - "当前设置:车下使用" 文本 (auto_id=1185)  → 宽1880 高38
  - "上翻页" 按钮       (auto_id=1013)        → 宽178
"""

import time, logging
from datetime import datetime
from typing import Optional
from pywinauto.findwindows import find_elements
from pywinauto import mouse

from . import BaseApp
from config import settings

logger = logging.getLogger("autocar.apps.dts")


class DtsApp(BaseApp):
    APP_EXE = r"C:\Program Files (x86)\DTS\DTS20220525\DTS650.exe"
    INSTANCE_MULTI = False

    # ── 启动确认（UIA 标准控件） ────────────────────

    def confirm(self, timeout: int = 30) -> bool:
        if not self.window and not self._wait_for_dts_window(timeout):
            return False
        for title in ("确认", "确定"):
            btn = self.window.child_window(title=title, control_type="Button")
            if btn.exists(timeout=3):
                btn.click()
                logger.info("✓ 点击确认")
                time.sleep(2)
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
                mouse.click(coords=(target_x, target_y))
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
                mouse.click(coords=(target_x, target_y))
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
        deadline = time.time() + timeout
        while time.time() < deadline:
            wins = find_elements(backend="uia", top_level_only=True)
            for w in wins:
                try:
                    if w.class_name == "CDTS650MainClass":
                        return self._connect_by_handle(w.handle, w.process_id)
                except Exception:
                    continue
            for w in wins:
                try:
                    if w.class_name == "#32770" and "DTS" in (w.name or ""):
                        return self._connect_by_handle(w.handle, w.process_id)
                except Exception:
                    continue
            time.sleep(0.5)
        return False

    def _wait_for_dts_window(self, timeout: int = 30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            wins = find_elements(backend="uia", top_level_only=True)
            for w in wins:
                try:
                    if w.class_name == "#32770":
                        for child in w.children():
                            if child.name == "确认":
                                return self._connect_by_handle(w.handle)
                except Exception:
                    continue
            time.sleep(0.5)
        return False

    def ensure_running(self, timeout: int = 30) -> bool:
        if self.connect_existing():
            return True
        logger.info(f"启动 DTS: {self.APP_EXE}")
        import subprocess

        proc = subprocess.Popen([self.APP_EXE])
        self._launched_by_us = True
        return self._wait_for_dts_window(timeout)
