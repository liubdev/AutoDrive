"""
截图工具 - 截取屏幕任意区域保存为模板

用法:
  # 1. 先截取全屏，找到目标区域
  python scripts/capture_template.py full

  # 2. 用鼠标框选区域截图（需要先知道坐标）
  python scripts/capture_template.py region 855 956 178 81 --name dts_confirm

  # 3. 截取整个窗口
  python scripts/capture_template.py window "DTS" --name dts_window
"""
import sys
from pathlib import Path

# 确保能找到项目
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.screenshot import ScreenCapture
from vision.locate import TEMPLATE_DIR
from pywinauto.findwindows import find_elements
from config import settings

import argparse


def main():
    parser = argparse.ArgumentParser(description="截图工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # full - 全屏截图
    sub.add_parser("full", help="截取全屏")

    # region - 区域截图
    r = sub.add_parser("region", help="截取指定区域")
    r.add_argument("left", type=int)
    r.add_argument("top", type=int)
    r.add_argument("right", type=int)
    r.add_argument("bottom", type=int)
    r.add_argument("--name", default="template", help="模板文件名（不含扩展名）")

    # window - 窗口截图
    w = sub.add_parser("window", help="截取窗口")
    w.add_argument("title", help="窗口标题关键字")
    w.add_argument("--name", default="window", help="模板文件名")

    args = parser.parse_args()
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    sct = ScreenCapture()

    if args.cmd == "full":
        path = sct.fullscreen()
        print(f"全屏截图: {path}")
        print(f"现在用图片查看器打开，找到目标按钮的坐标")

    elif args.cmd == "region":
        path = sct.region((args.left, args.top, args.right, args.bottom))
        # 同时复制一份到 templates
        import shutil
        tmpl_path = TEMPLATE_DIR / f"{args.name}.png"
        shutil.copy2(path, tmpl_path)
        print(f"区域截图: {path}")
        print(f"模板已保存: {tmpl_path}")
        print(f"用法: app.click_image('{args.name}.png')")

    elif args.cmd == "window":
        wins = find_elements(backend=settings.uia_backend, top_level_only=True)
        for w in wins:
            try:
                if args.title.lower() in (w.name or "").lower():
                    r = w.rectangle
                    path = sct.region((r.left, r.top, r.right, r.bottom))
                    tmpl_path = TEMPLATE_DIR / f"{args.name}.png"
                    import shutil
                    shutil.copy2(path, tmpl_path)
                    print(f"窗口截图: {path}")
                    print(f"模板已保存: {tmpl_path}")
                    return
            except Exception:
                continue
        print(f"未找到窗口: {args.title}")


if __name__ == "__main__":
    main()
