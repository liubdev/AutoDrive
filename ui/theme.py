"""
主题系统：固定浅色 × 强调色（teal 信号青）。

面向用户的商业产品，当前暂不提供外观主题切换，固定浅色与系统亮色一致：
  - 基底令牌固定为 LIGHT
  - 强调色默认 teal（信号青），预留 set_accent 供后续版本扩展
  - 不监听系统主题切换（浅色恒定，界面风格稳定）
  - 应用方式：令牌 → 渲染 QSS 模板 → app.setStyleSheet
"""

import logging
import re

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QGuiApplication

log = logging.getLogger("autodrive.ui.theme")

# 只替换 {标识符} 形式的令牌占位符，CSS 的 { ... } 花括号原样保留
_TOKEN_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def render_qss(template: str, tokens: dict) -> str:
    def repl(m):
        return str(tokens[m.group(1)])
    return _TOKEN_RE.sub(repl, template)

# ── 基底令牌（浅色为默认值，与效果图一致） ───────────

LIGHT = {
    "board": "#EEF1F6", "surface": "#FFFFFF", "panel": "#F7F9FC", "raise": "#FFFFFF",
    "line": "#E3E9F1", "tx": "#17213A", "mut": "#5C6B82", "dim": "#9AA6B8",
    "ok": "#16803C", "warn": "#B45309", "crit": "#C72B23",
    "cardbg": "#FFFFFF", "cardline": "#E5EBF2",
    "radius": "10px",
    "shadow": "rgba(16,24,40,0.06)",
}
DARK = {
    "board": "#0B0E13", "surface": "#121824", "panel": "#161E2B", "raise": "#1A2332",
    "line": "#223047", "tx": "#EAF0F8", "mut": "#8E9AAD", "dim": "#5B687A",
    "ok": "#3DDC84", "warn": "#F5A623", "crit": "#F05B55",
    "cardbg": "#121824", "cardline": "#223047",
    "radius": "8px",
    "shadow": "rgba(0,0,0,0.35)",
}

# 强调色（按主题给出 acc / 按钮悬停色 acc_hi / 文字色 acc_ink）
ACCENTS = {
    "teal": {
        "label": "信号青",
        "light": {"acc": "#0D9488", "acc_hi": "#0A7B71", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#2FD6C2", "acc_hi": "#55E2D0", "acc_ink": "#062019"},
    },
    "blue": {
        "label": "企业蓝",
        "light": {"acc": "#1F6FEB", "acc_hi": "#1A5ECB", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#4AA3DF", "acc_hi": "#6DB7E8", "acc_ink": "#06131D"},
    },
    "steel": {
        "label": "冷钢蓝",
        "light": {"acc": "#4A6FA5", "acc_hi": "#3F5F8C", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#6B9CC9", "acc_hi": "#8BB3DA", "acc_ink": "#0B1725"},
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
    acc = ACCENTS.get(accent, ACCENTS["teal"])[resolved]
    base.update(acc)
    # 派生色：卡片上的柔和强调 / 悬停 / 语义色浅底
    base["acc_soft"] = _mix(base["acc"], base["cardbg"], 0.86)
    base["acc_line"] = _mix(base["acc"], base["cardline"], 0.5)
    base["ok_soft"] = _mix(base["ok"], base["cardbg"], 0.92)
    base["warn_soft"] = _mix(base["warn"], base["cardbg"], 0.92)
    base["crit_soft"] = _mix(base["crit"], base["cardbg"], 0.92)
    base["warn_line"] = _mix(base["warn"], base["cardline"], 0.5)
    return base


# ── QSS 模板 ───────────────────────────────────────

QSS_TEMPLATE = """
* { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; outline: none; }
QWidget { color: {tx}; font-size: 13px; }
QToolTip { background: {surface}; color: {tx}; border: 1px solid {line}; border-radius: 5px; padding: 4px 8px; }
QMainWindow#AppWindow { background: {board}; }

/* 顶栏 */
QFrame#TBar { background: {surface}; border: none; border-bottom: 1px solid {line}; }
QLabel#Brand { color: {tx}; font-size: 15px; font-weight: 700; }
QLabel#BrandAcc { color: {acc}; font-size: 15px; font-weight: 700; }
QLabel#DevStatus { color: {dim}; font-size: 12px; }

/* 向导步骤条 */
QFrame#WizBar { background: {surface}; border: none; border-bottom: 1px solid {line}; }
QFrame#StepBtn { background: transparent; border-radius: 8px; }
QFrame#StepBtn:hover { background: {acc_soft}; }
QFrame#StepBtn QLabel#StepDot { color: {dim}; background: {panel}; border: 1.5px solid {dim}; border-radius: 11px; font-weight: 700; font-size: 12px; }
QFrame#StepBtn QLabel#StepLabel { color: {mut}; font-size: 13px; }
QFrame#StepBtn QLabel#StepSub { color: {dim}; font-size: 11px; }
QFrame#StepBtn[stepState="done"] QLabel#StepDot { background: {ok}; border-color: {ok}; color: #FFFFFF; }
QFrame#StepBtn[stepState="done"] QLabel#StepLabel { color: {mut}; }
QFrame#StepBtn[stepState="current"] QLabel#StepDot { background: {acc}; border-color: {acc}; color: {acc_ink}; }
QFrame#StepBtn[stepState="current"] QLabel#StepLabel { color: {tx}; font-weight: 700; }
QFrame#StepBtn[stepState="current"] QLabel#StepSub { color: {acc}; }
QFrame#StepBtn[stepState="next"] QLabel#StepDot { background: {panel}; }
QFrame#StepBtn[stepState="next"] QLabel#StepLabel { color: {dim}; }
QLabel#Conn { background: {line}; border-radius: 1px; }

/* 页面 */
QWidget#RunPage, QWidget#DataPage, QWidget#AiPage { background: {panel}; }
QLabel#SecTitle { color: {dim}; font-size: 11px; font-weight: 600; }
QLabel#SecCount { color: {dim}; font-family: Consolas, monospace; font-size: 11px; }

/* 主页（极简入口） */
QWidget#HomePage { background: {board}; }
QLabel#HomeTitle { color: {tx}; font-size: 32px; font-weight: 700; }
QLabel#HomeAcc { color: {acc}; font-size: 32px; font-weight: 700; }
QLabel#HomeSub { color: {mut}; font-size: 14px; }
QLabel#HomeFoot { color: {dim}; font-size: 11px; }
QPushButton#HomeStart { background: {acc}; color: {acc_ink}; border: none; border-radius: 10px; padding: 12px 40px; font-size: 15px; font-weight: 700; }
QPushButton#HomeStart:hover { background: {acc_hi}; }
QPushButton#HomeStart:disabled { background: {acc_soft}; color: {dim}; }

/* 按钮 */
QPushButton#Primary { background: {acc}; color: {acc_ink}; border: none; border-radius: 7px; padding: 8px 20px; font-weight: 600; font-size: 13px; }
QPushButton#Primary:hover { background: {acc_hi}; }
QPushButton#Primary:disabled { background: {acc_soft}; color: {dim}; }
QPushButton#Danger { background: {crit}; color: #FFFFFF; border: none; border-radius: 7px; padding: 8px 20px; font-weight: 600; font-size: 13px; }
QPushButton#Danger:hover { background: {crit_hi}; }
QPushButton#Danger:disabled { background: {crit_soft}; color: {dim}; }
QPushButton#Ghost { background: transparent; color: {mut}; border: 1px solid {line}; border-radius: 7px; padding: 7px 18px; font-size: 13px; }
QPushButton#Ghost:hover { background: {acc_soft}; color: {tx}; border-color: {acc_line}; }

/* 进度条 */
QProgressBar { background: {board}; border: none; border-radius: 4px; min-height: 8px; max-height: 8px; text-align: center; }
QProgressBar::chunk { background: {acc}; border-radius: 4px; }

/* 时间线步骤行 */
QFrame#StepRow { border-radius: 6px; }
QFrame#StepRow[st="done"] QLabel#StepIcon { background: {ok}; color: #FFFFFF; }
QFrame#StepRow[st="running"] QLabel#StepIcon { background: {acc}; color: {acc_ink}; }
QFrame#StepRow[st="error"] QLabel#StepIcon { background: {crit}; color: #FFFFFF; }
QFrame#StepRow[st="cancelled"] QLabel#StepIcon { background: {dim}; color: #FFFFFF; }
QFrame#StepRow[st="pending"] QLabel#StepIcon { background: {panel}; color: {dim}; border: 1px solid {line}; }
QLabel#StepIcon { border-radius: 9px; font-size: 11px; font-weight: 700; }
QLabel#StepName { color: {tx}; font-size: 13px; }
QFrame#StepRow[st="pending"] QLabel#StepName { color: {dim}; }
QFrame#StepRow[st="running"] QLabel#StepName { color: {acc}; font-weight: 600; }
QFrame#StepRow[st="error"] QLabel#StepName { color: {crit}; }
QLabel#StepNote { color: {dim}; font-size: 11px; font-family: Consolas, monospace; }

/* 日志 */
QPlainTextEdit#LogView { background: {cardbg}; border: 1px solid {cardline}; border-radius: 8px; color: {tx}; font-family: Consolas, monospace; font-size: 12px; selection-background-color: {acc_soft}; }
QPlainTextEdit#LogView:focus { border: 1px solid {acc_line}; }

/* 卡片 */
QFrame#Card, QFrame#DtcCard, QFrame#FlowCard, QFrame#AiCard, QFrame#Prio, QFrame#RunBar { background: {cardbg}; border: 1px solid {cardline}; border-radius: {radius}; }
QFrame#DtcCard[sev="crit"] { background: {crit_soft}; border-left: 3px solid {crit}; }
QFrame#DtcCard[sev="warn"] { background: {warn_soft}; border-left: 3px solid {warn}; }
QLabel#CardTitle { color: {tx}; font-size: 13px; font-weight: 600; }
QLabel#CardCount { color: {dim}; font-size: 11px; font-family: Consolas, monospace; }
QLabel#DtcCode { font-family: Consolas, monospace; font-size: 16px; font-weight: 700; }
QFrame#DtcCard[sev="crit"] QLabel#DtcCode { color: {crit}; }
QFrame#DtcCard[sev="warn"] QLabel#DtcCode { color: {warn}; }
QLabel#DtcName { color: {tx}; font-size: 13px; font-weight: 600; }
QLabel#DtcDesc { color: {mut}; font-size: 12px; }
QLabel#SevBadge { border-radius: 9px; padding: 2px 9px; font-size: 10px; font-weight: 700; }
QLabel#SevBadge[grade="now"] { background: {crit_soft}; color: {crit}; }
QLabel#SevBadge[grade="later"] { background: {acc_soft}; color: {acc}; }
QFrame#DtcCard[sev="crit"] QLabel#SevBadge { background: {crit_soft}; color: {crit}; }
QFrame#DtcCard[sev="warn"] QLabel#SevBadge { background: {warn_soft}; color: {warn}; }
QLabel#Chip { background: {raise}; border: 1px solid {line}; border-radius: 5px; color: {mut}; font-family: Consolas, monospace; font-size: 11px; padding: 2px 8px; }
QLabel#ChipLbl { color: {dim}; font-size: 10px; }
QLabel#FileChip { background: {cardbg}; border: 1px solid {cardline}; border-radius: 6px; color: {mut}; font-family: Consolas, monospace; font-size: 11px; padding: 4px 10px; }

/* AI 卡 */
QLabel#AiHeader { color: {dim}; font-size: 11px; font-weight: 600; }
QLabel#AiText { color: {tx}; font-size: 13px; line-height: 1.6; }
QLabel#CauseItem { color: {tx}; font-size: 13px; }
QLabel#PrioNum { background: {acc_soft}; color: {acc}; border-radius: 6px; font-family: Consolas, monospace; font-size: 12px; font-weight: 700; }
QFrame#Prio[warn="1"] QLabel#PrioNum { background: {warn_soft}; color: {warn}; }
QLabel#PrioTitle { color: {tx}; font-size: 13px; font-weight: 600; }
QLabel#PrioEv { color: {dim}; font-size: 11px; }
QLabel#Tier { border-radius: 9px; padding: 2px 8px; font-size: 10px; font-weight: 700; }
QLabel#Tier[grade="now"] { background: {crit_soft}; color: {crit}; }
QLabel#Tier[grade="later"] { background: {acc_soft}; color: {acc}; }
QLabel#Tier[grade="deep"] { background: {warn_soft}; color: {warn}; }
QFrame#Notice { background: {warn_soft}; border: 1px solid {warn_line}; border-radius: {radius}; }

/* 数据流表 */
QTableWidget#FlowTable { background: {cardbg}; border: 1px solid {cardline}; border-radius: {radius}; gridline-color: {line}; font-size: 12px; }
QTableWidget#FlowTable::item { padding: 6px 10px; border: none; border-bottom: 1px solid {line}; }
QTableWidget#FlowTable::item:selected { background: {acc_soft}; color: {tx}; }
QHeaderView::section { background: {board}; color: {dim}; border: none; border-bottom: 1px solid {line}; padding: 7px 10px; font-size: 10px; font-weight: 600; }
QTableWidget#FlowTable QTableCornerButton::section { background: {board}; border: none; }

/* 滚动区域（视口透明，透出页面底色，避免默认灰色） */
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* 滚动条 */
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: {line}; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: {dim}; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: {line}; border-radius: 5px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""


class ThemeManager(QObject):
    """主题单例：负责解析/切换/持久化主题。在主窗口初始化时注册。"""

    changed = Signal(str)   # 携带最终解析结果 resolved: light/dark

    _instance = None

    def __init__(self, app=None):
        super().__init__()
        self._app = app
        self._qs = QSettings(ORG, APP)
        # 外观固定浅色（商业产品暂不提供主题切换，界面风格恒定）
        self.theme = "light"
        self.accent = self._qs.value("ui/accent", "teal")
        if self.accent not in ACCENTS:
            self.accent = "teal"
        self.resolved = "light"
        self.tokens = build_tokens("light", self.accent)
        self._has_system_signal = False
        ThemeManager._instance = self

    # ── 系统主题 ──────────────────────────────────

    @classmethod
    def instance(cls) -> "ThemeManager":
        return cls._instance

    def _connect_system_theme(self):
        """Qt 6.5+：订阅系统主题切换信号（实时跟随）"""
        try:
            sh = QGuiApplication.styleHints()
            sh.colorSchemeChanged.connect(self._on_system_theme_changed)
            self._has_system_signal = True
        except Exception:
            self._has_system_signal = False

    def _on_system_theme_changed(self, *_):
        if self.theme == "system":
            self.apply()

    def system_is_dark(self) -> bool:
        """当前系统是否为深色主题"""
        try:
            cs = QGuiApplication.styleHints().colorScheme()
            if cs in (Qt.ColorScheme.Dark, Qt.ColorScheme.Light):
                return cs == Qt.ColorScheme.Dark
        except Exception:
            pass
        return self._registry_is_dark()

    def _registry_is_dark(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except Exception:
            return False

    # ── 应用 / 切换 ───────────────────────────────

    def resolve(self) -> str:
        # 固定浅色
        return "light"

    def apply(self):
        self.resolved = self.resolve()
        self.tokens = build_tokens(self.resolved, self.accent)
        self.tokens["crit_hi"] = _mix(self.tokens["crit"], "#FFFFFF", 0.14) \
            if self.resolved == "dark" else _mix(self.tokens["crit"], "#000000", 0.12)
        if self._app is not None:
            self._app.setStyleSheet(render_qss(QSS_TEMPLATE, self.tokens))
        self.changed.emit(self.resolved)
        log.info("theme applied: %s / %s", self.resolved, self.accent)

    def set_theme(self, theme: str):
        # 固定浅色：忽略任何切换请求（保留接口，后续版本再开放）
        if theme != "light":
            return
        self.theme = "light"
        self._qs.setValue("ui/theme", "light")
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
