"""
打包 AutoDrive 为 EXE

用法:
    pip install pyinstaller
    python build_exe.py

输出: dist/AutoDrive.exe
"""
import os, subprocess, shutil
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    print("=" * 50)
    print("  打包 AutoDrive → EXE")
    print("=" * 50)

    # 检测依赖
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ✗ 请先安装: pip install pyinstaller")
        return

    cmd = [
        "pyinstaller",
        "--onefile",                # 单文件 EXE
        "--windowed",               # 无控制台窗口
        "--name", "AutoDrive",
        "--add-data", f"automation{os.pathsep}automation",
        "--add-data", f"vision{os.pathsep}vision",
        "--add-data", f"config{os.pathsep}config",
        "--hidden-import", "winsdk",
        "--hidden-import", "winsdk.windows.media.ocr",
        "--hidden-import", "winsdk.windows.globalization",
        "--hidden-import", "pywinauto",
        "--hidden-import", "pywinauto.keyboard",
        "--hidden-import", "pywinauto.findwindows",
        "--hidden-import", "psutil",
        "--hidden-import", "mss",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        str(ROOT / "autogui.py"),
    ]

    print("  正在打包...")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    if result.returncode == 0:
        exe_path = ROOT / "dist" / "AutoDrive.exe"
        if exe_path.exists():
            print(f"  ✓ 打包成功: {exe_path}")
            print(f"    大小: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        print("  ✗ 打包失败")
        err = result.stderr[-2000:] if result.stderr else result.stdout[-2000:]
        print(err)

    # 清理临时文件
    for p in [ROOT / "build", ROOT / "AutoDrive.spec"]:
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()


if __name__ == "__main__":
    main()
