"""
AutoCar global settings
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Settings:
    # --- Paths ---
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    reports_dir: Path = field(init=False)
    config_file: Path = field(init=False)
    # DTS650 诊断程序路径（可在 data/config.json 覆盖）
    dts_exe: str = r"C:\Program Files (x86)\DTS\DTS20220525\DTS650.exe"
    # ── DTS 后台自动化 ──────────────────────────────────
    # True: DTS 全程在后台运行（消息式输入，不抢前台），用户看不到执行过程
    # False: 回退旧物理输入模式（DTS 在前台，鼠标/键盘直点）
    dts_background: bool = True
    # 隐藏方式: "offscreen"(移到屏幕外+去任务栏, 默认) / "normal"(仅靠主窗口置顶遮挡)
    dts_window_mode: str = "offscreen"
    # 启动 DTS 时直接最小化（减少启动瞬间闪现）
    dts_start_minimized: bool = True
    # 自动化期间主窗口置顶（DTS 始终在下方，最外层）
    dts_keep_topmost: bool = True
    # 自动化期间前台被抢则周期性夺回（True=用户不可切走）
    dts_keep_foreground: bool = True
    # True: 用计划任务以管理员启动 DTS，避免 UAC 弹窗（需 AutoDrive 同样管理员运行）
    dts_elevated: bool = False

    # --- Automation ---
    default_timeout: int = 10          # default element wait timeout (seconds)
    retry_interval: float = 0.5        # retry interval (seconds)
    action_delay: float = 0.2          # delay between actions (seconds)
    uia_backend: str = "uia"           # pywinauto backend: "uia" or "win32"

    # --- Vision ---
    screenshot_format: str = "png"
    ocr_lang: str = "zh-CN"            # Windows OCR 语言

    # --- AI (DeepSeek) ---
    ai_provider: str = "deepseek"      # deepseek（OpenAI 兼容，key 走环境变量或 config.json）
    ai_model: str = "deepseek-chat"
    ai_temperature: float = 0.2
    ai_max_tokens: int = 4000
    ai_timeout: int = 120
    api_key: Optional[str] = "sk-e3643a2956604e50be4ade6ef4bf8f5c"      # None → 回退环境变量 DEEPSEEK_API_KEY
    api_base: Optional[str] = "https://api.deepseek.com"

    # --- Logging ---
    log_level: str = "INFO"
    log_file_enabled: bool = True
    log_file_max_mb: int = 50

    def __post_init__(self):
        self.data_dir = self.project_root / "data"
        self.logs_dir = self.data_dir / "logs"
        self.reports_dir = self.data_dir / "reports"
        self.config_file = self.data_dir / "config.json"

        for d in [self.data_dir, self.logs_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._load_user_config()

    def _load_user_config(self):
        """Load user config overrides from JSON file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    overrides = json.load(f)
                for key, value in overrides.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
            except Exception as e:
                print(f"[AutoCar] Failed to load config: {e}")

    def save(self):
        """Save current config to file"""
        data = {k: v for k, v in asdict(self).items()
                if not k.endswith("_dir") and k != "config_file" and k != "project_root"}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)


# Global singleton
settings = Settings()
