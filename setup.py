import sys
from cx_Freeze import Executable, setup

# 1. 基础编译与依赖配置
build_exe_options = {
    "packages": ["os", "sys"],  # 需要强制包含的第三方库/模块
    "excludes": ["tkinter"],  # 排除用不到的大型库以减小安装包体积
    "include_files": [
        # "config.json"
    ],  # 需要随程序打包的静态资源（如配置文件、图片、数据库）
}

# 2. MSI 安装包特定参数配置
bdist_msi_options = {
    "add_to_path": True,  # 安装完成后，自动将软件安装路径添加到 Windows 系统环境变量 PATH
    "initial_target_dir": r"[ProgramFilesFolder]\MyPythonApp",  # 默认安装路径
    # "install_icon": "icon.ico",  # 在控制面板“添加/删除程序”列表中显示的软件图标
    "summary_data": {
        "author": "autodrive",
        "comments": "自动化测试工具安装包",
    },
}

# 3. 运行环境配置（控制台应用 vs 图形界面应用）
base = None
if sys.platform == "win32":
    # 如果是 GUI 图形界面程序，设置为 "gui" 可以运行时不弹出命令行黑色窗口
    base = "gui"

# 4. 可执行文件与快捷方式配置
executables = [
    Executable(
        script="main.py",  # 主程序入口文件
        base=base,
        icon="icon.ico",  # 生成的 .exe 文件图标
        shortcut_name="我的桌面工具",  # 快捷方式显示的名称
        shortcut_dir="DesktopFolder",  # 自动在桌面创建快捷方式（也可设为 "ProgramMenuFolder" 在开始菜单创建）
    )
]

# 5. 核心 setup 函数
setup(
    name="MyPythonApp",
    version="1.0.0",
    description="基于 cx_Freeze 构建的示例 MSI 安装包",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
