"""
主题系统：固定浅色 × 强调色（azure 科技蓝）。

面向用户的商业产品，当前暂不提供外观主题切换，固定浅色与系统亮色一致：
  - 基底令牌固定为 LIGHT
  - 强调色默认 azure（科技蓝 #3880F0，来自方案 E 手绘还原），预留 set_accent
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

# ── 基底令牌（浅色为默认值，方案 E：白/近黑 + 科技蓝，随 ct1/ct2 还原） ──

LIGHT = {
    "board": "#F7F9FC", "surface": "#FFFFFF", "panel": "#F7F9FC", "raise": "#FFFFFF",
    "line": "#E5E9F0", "tx": "#111827", "mut": "#5B6573", "dim": "#98A2B0",
    "ok": "#1FA982", "warn": "#D97706", "crit": "#D4442F",
    "cardbg": "#FFFFFF", "cardline": "#E5E9F0",
    "radius": "8px",
    "shadow": "rgba(17,24,39,0.06)",
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
# 默认 azure #3880F0 —— 方案 E 手绘还原提取出的两图一致主蓝。
ACCENTS = {
    "azure": {
        "label": "科技蓝",
        "light": {"acc": "#3880F0", "acc_hi": "#2B6FE4", "acc_ink": "#FFFFFF"},
        "dark":  {"acc": "#5BA0F5", "acc_hi": "#7FB5F7", "acc_ink": "#06131D"},
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
    acc = ACCENTS.get(accent, ACCENTS["azure"])[resolved]
    base.update(acc)
    # 派生色：卡片上的柔和强调 / 悬停 / 语义色浅底
    base["acc_soft"] = _mix(base["acc"], base["cardbg"], 0.86)
    base["acc_line"] = _mix(base["acc"], base["cardline"], 0.5)
    base["ok_soft"] = _mix(base["ok"], base["cardbg"], 0.92)
    base["ok_line"] = _mix(base["ok"], base["cardline"], 0.5)
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

/* 顶栏（方案 E：蓝盾标 + AutoDrive + v1.0.0 胶囊 + 设备状态 + 动作按钮） */
QFrame#TBar { background: {surface}; border: none; border-bottom: 1px solid {line}; }
QLabel#Brand { color: {tx}; font-size: 15px; font-weight: 800; letter-spacing: 0.4px; }
QLabel#DevStatus { color: {dim}; font-size: 12px; }
QLabel#VersionPill { background: {acc_soft}; color: {acc}; border: 1px solid {acc_line}; border-radius: 9px; padding: 2px 9px; font-size: 10px; font-weight: 600; }

/* 流程进度指示条（纯展示，不可点击；done=绿✓ current=蓝 current 数 next=灰） */
QFrame#PhaseBar { background: {surface}; border: none; }
QFrame#PhaseBar QLabel#StepDot { color: {dim}; background: {surface}; border: 1.5px solid {line}; border-radius: 12px; font-weight: 700; font-size: 12px; }
QFrame#PhaseBar QLabel#StepLabel { color: {mut}; font-size: 13px; }
QFrame#PhaseBar QLabel#StepSub { color: {dim}; font-size: 11px; }
QFrame#PhaseBar QLabel#StepDot[stepState="done"] { background: {ok}; border-color: {ok}; color: #FFFFFF; }
QFrame#PhaseBar QLabel#StepLabel[stepState="done"] { color: {mut}; }
QFrame#PhaseBar QLabel#StepDot[stepState="current"] { background: {acc}; border-color: {acc}; color: {acc_ink}; }
QFrame#PhaseBar QLabel#StepLabel[stepState="current"] { color: {tx}; font-weight: 700; }
QFrame#PhaseBar QLabel#StepSub[stepState="current"] { color: {acc}; }
QLabel#Conn { background: {line}; border-radius: 1px; }

/* 页面 */
QWidget#RunPage, QWidget#DataPage, QWidget#AiPage, QWidget#DiagnosticPage, QWidget#HomePage { background: {panel}; }
QLabel#SecTitle { color: {dim}; font-size: 11px; font-weight: 600; }
QLabel#SecCount { color: {dim}; font-family: Consolas, monospace; font-size: 11px; }

/* 主页：设备选择（方案 E 还原 ct1） */
QLabel#HomeTitle { color: {tx}; font-size: 22px; font-weight: 700; }
QLabel#HomeSub { color: {dim}; font-size: 13px; }
QFrame#DevCard { background: {cardbg}; border: 1px solid {cardline}; border-radius: {radius}; }
QFrame#DevCard:hover { border-color: {acc_line}; }
QFrame#DevCard[sel="on"] { background: {acc_soft}; border: 1.5px solid {acc}; }
QLabel#DevCardName { color: {tx}; font-size: 15px; font-weight: 700; }
QFrame#DevCard[sel="on"] QLabel#DevCardName { color: {acc}; }
QLabel#DevCardSub { color: {dim}; font-size: 11px; }
QFrame#DevCard[sel="on"] QLabel#DevCardSub { color: {acc}; }

/* 分析页顶部：面包屑（ct2：‹ 返回 / 车型 诊断） */
QPushButton#CrumbBack { background: transparent; color: {mut}; border: none; padding: 3px 6px; font-size: 13px; }
QPushButton#CrumbBack:hover { color: {acc}; }
QPushButton#CrumbBack:disabled { color: {dim}; }
QLabel#CrumbText { color: {tx}; font-size: 14px; font-weight: 700; }
QFrame#ActionBar { background: transparent; border: none; }

/* 按钮 */
QPushButton#Primary { background: {acc}; color: {acc_ink}; border: none; border-radius: 5px; padding: 8px 20px; font-weight: 600; font-size: 13px; }
QPushButton#Primary:hover { background: {acc_hi}; }
QPushButton#Primary:disabled { background: {acc_soft}; color: {dim}; }
QPushButton#Danger { background: {crit}; color: #FFFFFF; border: none; border-radius: 5px; padding: 8px 20px; font-weight: 600; font-size: 13px; }
QPushButton#Danger:hover { background: {crit_hi}; }
QPushButton#Danger:disabled { background: {crit_soft}; color: {dim}; }
QPushButton#Ghost { background: transparent; color: {mut}; border: 1px solid {line}; border-radius: 5px; padding: 7px 18px; font-size: 13px; }
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
QPlainTextEdit#LogView { background: {cardbg}; border: 1px solid {cardline}; border-radius: 6px; color: {tx}; font-family: Consolas, monospace; font-size: 12px; selection-background-color: {acc_soft}; }
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
QLabel#DevIcon { background: {acc_soft}; color: {acc}; border-radius: 6px; font-family: Consolas, monospace; font-size: 13px; font-weight: 700; }
QLabel#ChipLbl { color: {dim}; font-size: 10px; }
QLabel#FileChip { background: {cardbg}; border: 1px solid {cardline}; border-radius: 6px; color: {mut}; font-family: Consolas, monospace; font-size: 11px; padding: 4px 10px; }

/* 诊断卡 */
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

/* 诊断页：分析链路 */
QLabel#AiStageSub { color: {dim}; font-size: 11px; }
QLabel#AiVerdict { border-radius: 9px; padding: 2px 9px; font-size: 10px; font-weight: 700; }
QLabel#AiVerdict[verdict="locatable"] { background: {ok_soft}; color: {ok}; }
QLabel#AiVerdict[verdict="roadtest"] { background: {warn_soft}; color: {warn}; }
QLabel#AiVerdict[verdict="failed"] { background: {crit_soft}; color: {crit}; }
QPlainTextEdit#AiInput { background: {cardbg}; border: 1px solid {cardline}; border-radius: 6px; color: {tx}; font-size: 13px; padding: 8px 10px; selection-background-color: {acc_soft}; }
QPlainTextEdit#AiInput:focus { border: 1px solid {acc_line}; }

/* 分析状态徽标：分析中(灰) / 分析完成(绿) */
QLabel#AiBadge { border-radius: 10px; padding: 3px 12px; font-size: 11px; font-weight: 700; }
QLabel#AiBadge[state="running"] { background: {panel}; border: 1px solid {line}; color: {dim}; }
QLabel#AiBadge[state="done"] { background: {ok_soft}; border: 1px solid {ok_line}; color: {ok}; }

/* ct2 输入条：FAQ 快捷描述 + ✦ 单行输入 + 回形针 + 蓝色圆形发送 */
QPushButton#FaqChip { background: {raise}; border: 1px solid {line}; border-radius: 6px; color: {mut}; font-size: 12px; padding: 6px 10px; }
QPushButton#FaqChip:hover { background: {acc_soft}; border-color: {acc_line}; color: {acc}; }
QLineEdit#InputBar { background: {cardbg}; border: 1px solid {cardline}; border-radius: 6px; color: {tx}; font-size: 13px; padding: 9px 12px; selection-background-color: {acc_soft}; }
QLineEdit#InputBar:focus { border: 1px solid {acc}; }
QPushButton#SendBtn { background: transparent; border: none; }

/* ct2 摘要条：车型 / 问题 */
QFrame#SummaryBar { background: {surface}; border: 1px solid {cardline}; border-radius: {radius}; }
QLabel#SummaryText { color: {tx}; font-size: 13px; }

/* 方案 E · 维修报告（真实诊断结果，widget 渲染） */
QFrame#ConclHero { background: {acc_soft}; border-left: 4px solid {acc}; border-radius: {radius}; }
QLabel#ConclTitle { color: {tx}; font-size: 15px; font-weight: 700; }
QFrame#CauseCard { background: {cardbg}; border: 1px solid {cardline}; border-radius: {radius}; }
QLabel#CauseRank { background: {acc_soft}; color: {acc}; border-radius: 7px; font-family: Consolas, monospace; font-size: 13px; font-weight: 700; }
QLabel#CauseName { color: {tx}; font-size: 14px; font-weight: 700; }
QLabel#CauseProb { border-radius: 9px; padding: 2px 9px; font-size: 10px; font-weight: 700; }
QLabel#CauseProb[pl="high"] { background: {crit_soft}; color: {crit}; }
QLabel#CauseProb[pl="mid"] { background: {warn_soft}; color: {warn}; }
QLabel#CauseProb[pl="low"] { background: {acc_soft}; color: {acc}; }
QLabel#CauseStepsHead { color: {mut}; font-size: 11px; font-weight: 700; }
QFrame#GuideRow { background: transparent; }
QLabel#GuideCheck { background: {ok}; color: #FFFFFF; border-radius: 9px; font-size: 9px; font-weight: 700; }
QLabel#GuideText { color: {tx}; font-size: 13px; }

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
        self.accent = self._qs.value("ui/accent", "azure")
        if self.accent not in ACCENTS or self.accent in ("teal", "steel"):
            # teal/steel 为旧版默认强调色，本版统一升级为方案 E 科技蓝 azure
            self.accent = "azure"
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
