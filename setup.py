import sys
from pathlib import Path

# PySide6 6.11 使用惰性模块属性；cx_Freeze 8.x 的 Qt hook 需要先看到
# PySide6.QtCore，否则会在 resolve_name 阶段报 QtCore 不存在。
import PySide6.QtCore  # noqa: F401

from cx_Freeze import Executable, setup

ROOT = Path(__file__).resolve().parent
ICON = ROOT / "icon.ico"

# 1. 基础编译与依赖配置
build_exe_options = {
    "packages": ["ui", "automation", "config", "ai", "vision"],
    "excludes": ["tkinter"],
    "include_files": [
        (str(ROOT / "ui" / "theme.qss"), "ui/theme.qss"),
        (str(ROOT / "data" / "templates"), "data/templates"),
        (str(ROOT / "ai" / "templates"), "ai/templates"),
        (str(ROOT / "ai" / "knowledge"), "ai/knowledge"),
    ],
}

# 2. MSI 安装包特定参数配置
bdist_msi_options = {
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\AutoDrive",
    "all_users": True,
    "upgrade_code": "{B7D9D8AB-2E5A-4B82-9C27-5FEF7F6C9A21}",
    "summary_data": {
        "author": "RunchTech",
        "comments": "RunchTech 车辆诊断与自动化工具",
    },
}
if ICON.exists():
    bdist_msi_options["install_icon"] = str(ICON)

# 3. 运行环境配置（控制台应用 vs 图形界面应用）
base = None
if sys.platform == "win32":
    # 如果是 GUI 图形界面程序，设置为 "gui" 可以运行时不弹出命令行黑色窗口
    base = "gui"

# 4. 可执行文件与快捷方式配置
executables = [
    Executable(
        script="autogui.py",
        base=base,
        icon=str(ICON) if ICON.exists() else None,
        shortcut_name="AutoDrive",
        shortcut_dir="ProgramMenuFolder",
    )
]

# 5. 核心 setup 函数
setup(
    name="AutoDrive",
    version="1.0.0",
    description="RunchTech 车辆诊断与自动化工具",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
