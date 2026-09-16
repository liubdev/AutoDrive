"""兼容入口：实际实现位于 scripts/tools/build_knowledge.py。"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "tools" / "build_knowledge.py"),
        run_name="__main__",
    )
