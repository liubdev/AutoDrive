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

    # --- Automation ---
    default_timeout: int = 10          # default element wait timeout (seconds)
    retry_interval: float = 0.5        # retry interval (seconds)
    action_delay: float = 0.2          # delay between actions (seconds)
    uia_backend: str = "uia"           # pywinauto backend: "uia" or "win32"

    # --- Vision ---
    screenshot_format: str = "png"
    ocr_lang: str = "chi_sim+eng"      # Tesseract language pack

    # --- AI ---
    ai_provider: str = "openai"        # openai / azure / local
    ai_model: str = "gpt-4o"
    ai_temperature: float = 0.1
    ai_max_tokens: int = 2000
    api_key: Optional[str] = None
    api_base: Optional[str] = None

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
