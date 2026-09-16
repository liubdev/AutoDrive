"""兼容入口：实际实现位于 scripts/tools/run_dts.py。"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "tools" / "run_dts.py"),
        run_name="__main__",
    )
