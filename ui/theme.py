"""
主题系统：深色默认 + 浅色切换（LCS700 双模式）。

设计源：docs/RunchTech_V01.html —— 深色默认（近黑蓝 + 青蓝强调），
浅色模式等值切换；强调色固定「sky」品牌渐变 #38bdf8→#2563eb。

  - 持久化：QSettings `ui/mode`（"dark" | "light"，默认 "dark"）。
    ⚠️ 忽略旧版 `ui/theme` 键（旧版恒写 "light"），保证升级后深色默认。
  - 强调色：QSettings `ui/accent` 默认 "sky"。
  - 应用方式：build_tokens() → render_qss(QSS_TEMPLATE) → app.setStyleSheet，
    并对 allWidgets() 逐个 update()（QPainter 控件读令牌重绘）+ 打 ui/mode 属性。
"""

import logging
import re

from PySide6.QtCore import QObject, QSettings, QTimer, Signal
from PySide6.QtWidgets import QWidget

from ui import theme_qss

log = logging.getLogger("autodrive.ui.theme")

# 只替换 {标识符} 形式的令牌占位符，CSS 的 { ... } 花括号原样保留
_TOKEN_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def render_qss(template: str, tokens: dict) -> str:
    def repl(m):
        return str(tokens[m.group(1)])
    return _TOKEN_RE.sub(repl, template)


# ── 基底令牌（LCS700 色板，深色默认） ──

LIGHT = {
    "board": "#f3f5f9", "surface": "#f3f5f9", "panel": "#ffffff", "raise": "#ffffff",
    "line": "#dde1e8", "tx": "#1f2937", "mut": "#4b5563", "dim": "#6b7280",
    "ok": "#16a34a", "warn": "#ea580c", "crit": "#dc2626",
    "acc": "#2563eb", "acc_hi": "#1d4ed8",
    "cyan": "#2563eb", "cyan_soft": "#2563eb",
    "topbar": "#fbfcfd", "bottomb": "#fbfcfd",
    "radius": "14px",
    "shadow": "rgba(0,0,0,0.06)",
}
DARK = {
    "board": "#0b0e14", "surface": "#0e131c", "panel": "#141a24", "raise": "#1e242e",
    "line": "#232a34", "tx": "#e5e7eb", "mut": "#9ca3af", "dim": "#6b7280",
    "ok": "#34d399", "warn": "#fb923c", "crit": "#f87171",
    "acc": "#38bdf8", "acc_hi": "#7dd3fc",
    "cyan": "#22d3ee", "cyan_soft": "#7dd3fc",
    "topbar": "#12151c", "bottomb": "#12151c",
    "radius": "14px",
    "shadow": "rgba(0,0,0,0.35)",
}

# 主题无关的固定色（品牌渐变 / 语义渐变 / 按钮文字）
FIXED = {
    "acc_grad0": "#38bdf8", "acc_grad1": "#2563eb",
    "ok_grad0": "#10b981", "ok_grad1": "#059669",
    "acc_ink": "#FFFFFF",
}

# 强调色（sky 为默认；保留旧 accent 值兼容历史 QSettings）
ACCENTS = {
    "sky": {
        "label": "远驰青",
        "light": {"acc": "#2563eb", "acc_hi": "#1d4ed8", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#38bdf8", "acc_hi": "#7dd3fc", "acc_ink": "#FFFFFF"},
    },
    "azure": {
        "label": "科技蓝",
        "light": {"acc": "#2563eb", "acc_hi": "#1d4ed8", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#38bdf8", "acc_hi": "#7dd3fc", "acc_ink": "#FFFFFF"},
    },
    "blue": {
        "label": "企业蓝",
        "light": {"acc": "#1F6FEB", "acc_hi": "#1A5ECB", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#4AA3DF", "acc_hi": "#6DB7E8", "acc_ink": "#06131D"},
    },
    "steel": {
        "label": "工程蓝",
        "light": {"acc": "#2C5F8F", "acc_hi": "#27517D", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#6B9CC9", "acc_hi": "#8BB3DA", "acc_ink": "#0B1725"},
    },
    "teal": {
        "label": "信号青",
        "light": {"acc": "#0D9488", "acc_hi": "#0A7B71", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#2FD6C2", "acc_hi": "#55E2D0", "acc_ink": "#062019"},
    },
}

ORG, APP = "AutoDrive", "AutoDrive"


def _mix(a: str, b: str, t: float) -> str:
    """把颜色 a 朝 b 混合 t 比例（t=0 全 a，t=1 全 b），返回 #rrggbb"""
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    x, y = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(p + (q - p) * t) for p, q in zip(x, y))


def build_tokens(resolved: str, accent: str) -> dict:
    """合并基底 + 强调色 + 派生混合色，得到一份完整令牌表"""
    base = dict(DARK if resolved == "dark" else LIGHT)
    base.update(FIXED)
    acc = ACCENTS.get(accent, ACCENTS["sky"])[resolved]
    base.update(acc)
    # 兼容别名（旧模板/旧代码引用）
    base["cardbg"] = base["panel"]
    base["cardline"] = base["line"]
    # 派生色：柔和强调 / 强调描边 / 语义色浅底
    base["acc_soft"] = _mix(base["acc"], base["panel"], 0.86)
    base["acc_line"] = _mix(base["acc"], base["line"], 0.5)
    base["ok_soft"] = _mix(base["ok"], base["panel"], 0.92)
    base["ok_line"] = _mix(base["ok"], base["line"], 0.5)
    base["warn_soft"] = _mix(base["warn"], base["panel"], 0.92)
    base["warn_line"] = _mix(base["warn"], base["line"], 0.5)
    base["crit_soft"] = _mix(base["crit"], base["panel"], 0.92)
    base["crit_line"] = _mix(base["crit"], base["line"], 0.5)
    # 毛玻璃底（Qt 无 backdrop-blur，用半透明近似）
    base["glass"] = "rgba(255,255,255,0.05)" if resolved == "dark" else "rgba(255,255,255,0.55)"
    base["glass_line"] = base["line"]
    # 输入条底色
    base["input_bg"] = "#0b0e14" if resolved == "dark" else "#f9fafb"
    return base


class ThemeManager(QObject):
    """主题单例：解析/切换/持久化双模式主题。在主窗口初始化时注册。"""

    changed = Signal(str)   # 携带最终解析结果 resolved: light/dark

    _instance = None

    def __init__(self, app=None):
        super().__init__()
        self._app = app
        self._qs = QSettings(ORG, APP)
        # 双模式默认深色；旧键 ui/theme（恒写 light）被忽略
        self.theme = self._qs.value("ui/mode", "dark")
        if self.theme not in ("dark", "light"):
            self.theme = "dark"
        self.accent = self._qs.value("ui/accent", "sky")
        if self.accent not in ACCENTS:
            self.accent = "sky"
        self.resolved = self.theme
        self.tokens = build_tokens(self.theme, self.accent)
        # 渲染缓存：仅当 (模板, 模式, 强调色) 变化才重跑正则替换
        self._css_key = None
        self._css = ""
        self._pending_apply = False
        ThemeManager._instance = self

    @classmethod
    def instance(cls) -> "ThemeManager":
        return cls._instance

    # ── 应用 / 切换 ───────────────────────────

    def resolve(self) -> str:
        return self.theme

    def apply(self):
        self.resolved = self.resolve()
        self.tokens = build_tokens(self.resolved, self.accent)
        self.tokens["crit_hi"] = _mix(self.tokens["crit"], "#FFFFFF", 0.14) \
            if self.resolved == "dark" else _mix(self.tokens["crit"], "#000000", 0.12)
        if self._app is not None:
            # 第一拍（同步）：打 ui/mode 动态属性，便宜，且必须先于 setStyleSheet
            # 供属性选择器匹配；属性变化本身不触发重绘，不会造成闪烁。
            for w in self._app.allWidgets():
                try:
                    w.setProperty("ui/mode", self.resolved)
                except Exception:
                    pass
            # 第二拍（下一事件循环）：setStyleSheet + 仅可见控件 update ——
            # 让按钮点击事件先返回，把全量 repolish 冻结移出事件栈。
            if not self._pending_apply:
                self._pending_apply = True
                QTimer.singleShot(0, self._apply_sheet)
        else:
            self.changed.emit(self.resolved)
        log.info("theme apply scheduled: %s / %s", self.resolved, self.accent)

    def _apply_sheet(self):
        """第二拍：真正应用样式表 + 重绘可见控件。"""
        self._pending_apply = False
        if self._app is None:
            return
        try:
            self._app.setStyleSheet(self._render_css())
        except Exception:
            pass
        # QPainter 控件 paintEvent 读 tokens，只需重绘可见控件；隐藏页在
        # setStyleSheet 时已被标记 dirty，下次显示会以新样式绘制。
        for w in self._app.allWidgets():
            try:
                if w.isVisible():
                    w.update()
            except Exception:
                pass
        self.changed.emit(self.resolved)
        log.info("theme applied: %s / %s", self.resolved, self.accent)

    def _render_css(self) -> str:
        """渲染 QSS（模板/模式/强调色任一变化才重跑正则替换）。"""
        tpl = theme_qss.QSS_TEMPLATE
        key = (tpl, self.resolved, self.accent)
        if self._css_key == key:
            return self._css
        self._css = render_qss(tpl, self.tokens)
        self._css_key = key
        return self._css

    def apply_to(self, widget):
        """对单个页面子树打 ui/mode 属性并重绘（懒加载页构建后复用，避免整窗 apply）。"""
        try:
            for w in [widget] + widget.findChildren(QWidget):
                try:
                    w.setProperty("ui/mode", self.resolved)
                except Exception:
                    pass
            widget.update()
        except Exception:
            pass

    def set_theme(self, theme: str):
        if theme not in ("dark", "light"):
            return
        self.theme = theme
        self._qs.setValue("ui/mode", theme)
        self.apply()

    def set_accent(self, accent: str):
        if accent not in ACCENTS:
            return
        self.accent = accent
        self._qs.setValue("ui/accent", accent)
        self.apply()

    @property
    def accent_label(self) -> str:
        return ACCENTS.get(self.accent, {}).get("label", self.accent)
