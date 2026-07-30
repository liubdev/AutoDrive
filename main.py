"""
AutoDrive - Windows 应用自动化
"""

import sys, io, json, logging
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    command = sys.argv[1]
    if command == "script":
        cmd_script()
    else:
        print_usage()


def print_usage():
    print("""
AutoDrive - Windows 应用自动化

用法:
  python main.py script <script.py>    执行自动化脚本

示例:
  python main.py script scripts/run_dts.py
""")


def cmd_script():
    """执行 Python 脚本"""
    if len(sys.argv) < 3:
        print("用法: python main.py script <script.py>")
        return
    script_path = sys.argv[2]
    script_file = Path(script_path)
    if not script_file.exists():
        print(f"脚本不存在: {script_path}")
        return

    script_globals = {
        "__file__": str(script_file),
    }
    print(f"执行: {script_path}")
    try:
        exec(script_file.read_text(encoding="utf-8"), script_globals)
    except Exception as e:
        logging.error(f"脚本失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
