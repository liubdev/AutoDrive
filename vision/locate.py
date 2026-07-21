"""
Vision-based element locator - 图片定位 + OCR 文字定位 + 自适应分辨率

什么时候用:
  UIA 找不到控件时（自绘控件、图片按钮、XAML Island、Web 控件）

三种定位方式:
  1. find_image(template)   → 模板匹配（按钮截图）
  2. find_text(text)        → OCR 文字定位
  3. find_color(color)      → 颜色匹配（特殊形状）

分辨率自适应:
  - 所有坐标返回时已做 DPI 缩放校正
  - 模板匹配在窗口缩放时自动缩放模板
"""

import time
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

import cv2
import numpy as np
from mss import mss
from pywinauto import Desktop
from pywinauto.findwindows import find_elements

from config import settings
from vision.screenshot import ScreenCapture

logger = logging.getLogger("autocar.vision.locate")

TEMPLATE_DIR = settings.project_root / "data" / "templates"


# ── 定位结果 ────────────────────────────────────────────


@dataclass
class LocateResult:
    """定位结果"""

    x: int  # 屏幕坐标（已校正 DPI）
    y: int
    confidence: float  # 匹配置信度 0~1
    width: int  # 匹配区域宽
    height: int  # 匹配区域高
    method: str  # 定位方式: template/ocr/color

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


# ── 图片定位器 ──────────────────────────────────────────


class ImageLocator:
    """
    图片/文字定位器

    用法:
      locator = ImageLocator()

      # 方式1: 模板匹配（需要先截图保存按钮图片）
      result = locator.find_image("dts_confirm.png")
      if result:
          locator.click(result)

      # 方式2: OCR 文字定位
      result = locator.find_text("确认")
      if result:
          locator.click(result)
    """

    def __init__(self):
        self._sct = ScreenCapture()
        self._mss = mss()

    # ── 模板匹配 ──────────────────────────────────────────

    def find_image(
        self,
        template_name: str,
        window_handle: int = None,
        threshold: float = 0.8,
        scale_range: Tuple[float, float] = (0.5, 1.5),
    ) -> Optional[LocateResult]:
        """
        在屏幕/窗口中查找模板图片

        Args:
            template_name: 模板文件名（在 data/templates/ 下）
                           e.g. "dts_confirm.png"
            window_handle: 限定搜索范围（窗口句柄），None=全屏
            threshold: 匹配阈值（0~1），越高越严格
            scale_range: 缩放搜索范围（应对不同分辨率）

        Returns:
            LocateResult 或 None
        """
        template_path = TEMPLATE_DIR / template_name
        if not template_path.exists():
            logger.error(f"模板不存在: {template_path}")
            return None

        # 1. 读取模板
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            logger.error(f"无法读取模板: {template_path}")
            return None
        th, tw = template.shape

        # 2. 截取目标区域
        screen_img = self._capture_region(window_handle)
        if screen_img is None:
            return None

        # 3. 多尺度模板匹配（应对不同分辨率）
        best_val = -1
        best_loc = None
        best_scale = 1.0

        scale = scale_range[0]
        while scale <= scale_range[1]:
            # 缩放模板
            w_scaled = int(tw * scale)
            h_scaled = int(th * scale)
            if w_scaled < 10 or h_scaled < 10:
                scale += 0.1
                continue

            scaled = cv2.resize(template, (w_scaled, h_scaled))

            if (
                scaled.shape[0] > screen_img.shape[0]
                or scaled.shape[1] > screen_img.shape[1]
            ):
                scale += 0.1
                continue

            # 模板匹配
            result = cv2.matchTemplate(screen_img, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_scale = scale

            scale += 0.1

        # 4. 判断结果
        if best_val >= threshold:
            x, y = best_loc
            w = int(tw * best_scale)
            h = int(th * best_scale)

            # 如果是窗口区域截图，需要偏移到屏幕坐标
            offset_x, offset_y = self._get_window_offset(window_handle)
            screen_x = x + offset_x
            screen_y = y + offset_y

            logger.info(
                f"✓ 图片匹配 '{template_name}': "
                f"({screen_x},{screen_y}) conf={best_val:.2f}"
            )
            return LocateResult(
                x=screen_x,
                y=screen_y,
                confidence=best_val,
                width=w,
                height=h,
                method="template",
            )
        else:
            logger.warning(
                f"✗ 图片匹配失败 '{template_name}': "
                f"最高置信度={best_val:.2f} (需≥{threshold})"
            )
            return None

    # ── OCR 文字定位 ──────────────────────────────────────

    def find_text(
        self,
        text: str,
        window_handle: int = None,
    ) -> Optional[LocateResult]:
        """
        通过 OCR 在屏幕/窗口中查找文字位置

        Args:
            text: 要查找的文字（支持中文）
            window_handle: 限定搜索范围

        Returns:
            LocateResult 或 None
        """
        try:
            from vision.ocr import OCR

            ocr = OCR()
            if not ocr.is_available():
                logger.error("OCR 不可用")
                return None

            # 截图
            img_path = self._sct.region(
                self._get_window_rect(window_handle)
                if window_handle
                else (0, 0, 1920, 1080)  # fallback, 全屏
            )

            # OCR 搜索
            box = ocr.search_text(img_path, text)
            if box:
                offset_x, offset_y = self._get_window_offset(window_handle)
                screen_x = box["x"] + offset_x
                screen_y = box["y"] + offset_y

                logger.info(
                    f"✓ OCR 找到 '{text}': "
                    f"({screen_x},{screen_y}) conf={box['conf']}"
                )
                return LocateResult(
                    x=screen_x,
                    y=screen_y,
                    confidence=box["conf"] / 100.0,
                    width=box["w"],
                    height=box["h"],
                    method="ocr",
                )
        except Exception as e:
            logger.warning(f"OCR 定位失败: {e}")
        return None

    # ── 颜色匹配 ──────────────────────────────────────────

    def find_color(
        self,
        color: Tuple[int, int, int],
        window_handle: int = None,
        tolerance: int = 30,
    ) -> Optional[LocateResult]:
        """
        按颜色查找区域（适用于形状特殊但颜色固定的按钮）

        Args:
            color: RGB 颜色值 (R, G, B)
            window_handle: 限定窗口
            tolerance: 颜色容差
        """
        screen_img = self._capture_region(window_handle, color=True)
        if screen_img is None:
            return None

        # BGR 颜色范围
        lower = np.array([max(0, c - tolerance) for c in color[::-1]])
        upper = np.array([min(255, c + tolerance) for c in color[::-1]])

        mask = cv2.inRange(screen_img, lower, upper)

        # 找最大的连通区域
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        offset_x, offset_y = self._get_window_offset(window_handle)
        logger.info(f"✓ 颜色匹配 ({color}): ({x+offset_x},{y+offset_y}) area={w*h}")
        return LocateResult(
            x=x + offset_x,
            y=y + offset_y,
            confidence=1.0,
            width=w,
            height=h,
            method="color",
        )

    # ── 点击操作 ──────────────────────────────────────────

    def click(self, result: LocateResult, button: str = "left") -> bool:
        """
        在定位结果位置点击

        Args:
            result: 定位结果
            button: left / right
        """
        cx, cy = result.center
        try:
            import pywinkey

            # 使用 pywinauto 模拟点击
            from pywinauto import mouse

            mouse.click(button=button, coords=(cx, cy))
            logger.info(f"  点击 ({cx}, {cy})")
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.warning(f"鼠标点击失败: {e}")
            return False

    def double_click(self, result: LocateResult) -> bool:
        """双击"""
        cx, cy = result.center
        try:
            from pywinauto import mouse

            mouse.double_click(coords=(cx, cy))
            return True
        except Exception:
            return False

    def right_click(self, result: LocateResult) -> bool:
        """右键"""
        cx, cy = result.center
        try:
            from pywinauto import mouse

            mouse.click(button="right", coords=(cx, cy))
            return True
        except Exception:
            return False

    # ── 内部方法 ──────────────────────────────────────────

    def _capture_region(
        self, window_handle: int = None, color: bool = False
    ) -> Optional[np.ndarray]:
        """截图指定区域，返回 OpenCV 图像"""
        if window_handle:
            # 截窗口区域
            rect = self._get_window_rect(window_handle)
            if rect is None:
                return None
            left, top, right, bottom = rect
        else:
            # 全屏
            mon = self._mss.monitors[1]
            left, top = mon["left"], mon["top"]
            right = left + mon["width"]
            bottom = top + mon["height"]

        # 用 mss 截图（比 PIL 快）
        monitor = {
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
        }
        sct_img = self._mss.grab(monitor)
        img = np.array(sct_img)

        if color:
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        else:
            return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

    def _get_window_rect(self, handle: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口矩形 (left, top, right, bottom)"""
        try:
            wins = find_elements(backend=settings.uia_backend, top_level_only=True)
            for w in wins:
                if w.handle == handle:
                    r = w.rectangle
                    return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
        return None

    def _get_window_offset(self, handle: int = None) -> Tuple[int, int]:
        """获取窗口相对屏幕的偏移"""
        if handle is None:
            return (0, 0)
        rect = self._get_window_rect(handle)
        if rect:
            return (rect[0], rect[1])
        return (0, 0)


# ── 分辨率自适应工具 ──────────────────────────────────────


class ResolutionAdapter:
    """
    分辨率适配器

    用法:
      adapter = ResolutionAdapter(reference=(1920, 1080))
      x, y = adapter.scale(855, 956)  # 将参考分辨率坐标映射到当前屏幕
    """

    def __init__(self, reference: Tuple[int, int] = (1920, 1080)):
        self.ref_w, self.ref_h = reference
        self._current = None

    @property
    def current(self) -> Tuple[int, int]:
        """获取当前屏幕分辨率"""
        if self._current is None:
            mon = mss().monitors[1]
            self._current = (mon["width"], mon["height"])
        return self._current

    def scale_x(self, x: int) -> int:
        """X 坐标缩放"""
        cw, _ = self.current
        return int(x * cw / self.ref_w)

    def scale_y(self, y: int) -> int:
        """Y 坐标缩放"""
        _, ch = self.current
        return int(y * ch / self.ref_h)

    def scale(self, x: int, y: int) -> Tuple[int, int]:
        """坐标缩放"""
        return (self.scale_x(x), self.scale_y(y))

    def scale_rect(
        self, left: int, top: int, right: int, bottom: int
    ) -> Tuple[int, int, int, int]:
        """矩形区域缩放"""
        return (
            self.scale_x(left),
            self.scale_y(top),
            self.scale_x(right),
            self.scale_y(bottom),
        )

    def window_relative(self, win_handle: int, x: int, y: int) -> Tuple[float, float]:
        """
        屏幕坐标 → 窗口内相对比例（0~1）

        用于跨分辨率：存相对比例，在不同分辨率下还原
        """
        from pywinauto.findwindows import find_elements

        wins = find_elements(backend=settings.uia_backend, top_level_only=True)
        for w in wins:
            if w.handle == win_handle:
                r = w.rectangle
                rx = (x - r.left) / r.width()
                ry = (y - r.top) / r.height()
                return (rx, ry)
        return (0, 0)

    def screen_from_relative(
        self, win_handle: int, rx: float, ry: float
    ) -> Tuple[int, int]:
        """
        窗口内相对比例 → 屏幕坐标

        用法: 在 1920x1080 上记录按钮的相对位置 (0.5, 0.8)
              在 2560x1440 上还原为屏幕坐标
        """
        from pywinauto.findwindows import find_elements

        wins = find_elements(backend=settings.uia_backend, top_level_only=True)
        for w in wins:
            if w.handle == win_handle:
                r = w.rectangle
                sx = int(r.left + rx * r.width())
                sy = int(r.top + ry * r.height())
                return (sx, sy)
        return (0, 0)
