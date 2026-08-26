"""
打包 AutoDrive 为 EXE（Nuitka onefile）

用法:
    pip install nuitka
    python build_exe.py

前置要求（Windows）:
    Nuitka onefile 需要 C 编译器：安装 Visual Studio 2022 Build Tools
    （组件勾选「使用 C++ 的桌面开发」即可，无需打开 VS）。

输出: dist/AutoDrive.exe
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def _have_msvc() -> bool:
    """用 vswhere 探测 VS/Build Tools 是否含 MSVC x64 工具链"""
    pf = os.environ.get("ProgramFiles(x86)")
    if not pf:
        return False
    vswhere = Path(pf) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.exists():
        return False
    try:
        out = subprocess.run(
            [str(vswhere), "-latest", "-products", "*",
             "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
             "-property", "installationPath"],
            capture_output=True, text=True, timeout=15)
        return out.returncode == 0 and out.stdout.strip() != ""
    except Exception:
        return False


def main():
    print("=" * 50)
    print("  打包 AutoDrive → EXE（Nuitka）")
    print("=" * 50)

    # 1) Nuitka
    try:
        import nuitka  # noqa: F401
        print("  ✓ Nuitka 已安装")
    except ImportError:
        print("  ✗ 请先安装: pip install nuitka")
        return

    # 2) MSVC 前置检查（Nuitka onefile 在 Windows 必须用 C 编译器）
    if not _have_msvc():
        print("  ! 未检测到 MSVC 编译器（Visual Studio 2022 Build Tools）")
        print("    安装地址: https://visualstudio.microsoft.com/visual-cpp-build-tools/")
        print("    安装时勾选「使用 C++ 的桌面开发」，然后重试本脚本。")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",                     # 单文件 EXE
        "--windows-console-mode=disable",  # 无控制台窗口
        "--enable-plugin=pyside6",
        "--output-dir=dist",             # 输出 dist/AutoDrive.exe（与旧版一致）
        "--output-filename=AutoDrive.exe",
        # 第三方依赖（含动态导入的子模块，对应旧 PyInstaller 的 --hidden-import）
        "--include-package=pywinauto",
        "--include-module=pywinauto.keyboard",
        "--include-module=pywinauto.findwindows",
        "--include-package=winsdk",
        "--include-module=winsdk.windows.media.ocr",
        "--include-module=winsdk.windows.globalization",
        "--include-package=PIL",
        "--include-package=mss",
        "--include-package=psutil",
        "--include-package=cv2",
        "--include-package=numpy",
        # 数据目录（模板 + 知识库 + 配置 + 流程/视觉素材）
        "--include-data-dir=automation=automation",
        "--include-data-dir=vision=vision",
        "--include-data-dir=config=config",
        "--include-data-dir=ai=ai",
        str(ROOT / "autogui.py"),
    ]

    print("  正在打包（onefile 首次编译约 5–20 分钟，请耐心等待）...")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")

    log_path = ROOT / "build_exe.log"
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")

    exe_path = ROOT / "dist" / "AutoDrive.exe"
    if result.returncode == 0 and exe_path.exists():
        print(f"  ✓ 打包成功: {exe_path}")
        print(f"    大小: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"    构建日志: {log_path.name}")
    else:
        print("  ✗ 打包失败，详见 build_exe.log 末尾：")
        tail = "\n".join(log_path.read_text(encoding="utf-8").splitlines()[-20:])
        print(tail)

    # 清理中间目录（保留 dist 与日志）
    for p in [ROOT / "autogui.build", ROOT / "autogui.onefile-build"]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


if __name__ == "__main__":
    main()
