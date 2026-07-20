#!/usr/bin/env python3
"""
AutoCar - Windows EXE smart automation framework
Control-driven (UIA) + AI + Vision.
"""

import sys
import io

# Force UTF-8 for stdout/stderr (Windows cp1252 workaround)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import logging
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import settings
from agent import AutoController, Workflow

# -- Logging setup --

def setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    logging.basicConfig(
        level=level, format=fmt, datefmt=datefmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if settings.log_file_enabled:
        log_file = settings.logs_dir / "autocar.log"
        fh = logging.FileHandler(log_file, encoding="utf-8", mode="a")
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        logging.getLogger("autocar").addHandler(fh)
        logging.getLogger("autocar").info(f"Log file: {log_file}")

    return logging.getLogger("autocar")


logger = setup_logging()


# -- Entry point --

def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command == "run":
        cmd_run()
    elif command == "explore":
        cmd_explore()
    elif command == "inspect":
        cmd_inspect()
    elif command == "script":
        cmd_script()
    elif command == "goal":
        cmd_goal()
    elif command == "record":
        cmd_record()
    elif command in ("-h", "--help", "help"):
        print_usage()
    else:
        print(f"Unknown command: {command}")
        print_usage()


def print_usage():
    print(r"""
  ___         _        ___              _
 / _ \       | |      / __|_ _ ___ __ _(_)_ _
| (_) |_ _ __| |_____| (__| '_/ -_) _` | | ' \
 \___/___|_  |_|      \___|_| \___\__,_|_|_||_|
         |_|

Windows EXE automation framework - control-driven + AI + vision

Usage:
  python main.py run <exe_path> [script.json]   Execute automation script
  python main.py explore [window_title]          Interactive UI probe
  python main.py inspect <exe_path>             Launch and inspect controls
  python main.py script <script.py>              Run Python automation script
  python main.py goal "<desc>" [exe_path]        AI-driven goal execution
  python main.py record <exe_path> [duration]    Record action snapshots

Examples:
  python main.py explore "Chrome"
  python main.py inspect mspaint.exe
  python main.py goal "Open notepad, type Hello" notepad.exe
""")


# -- Commands --

def cmd_run():
    """Execute automation steps from JSON"""
    if len(sys.argv) < 3:
        print("Usage: python main.py run <exe_path> [script.json]")
        return

    exe_path = sys.argv[2]
    script_path = sys.argv[3] if len(sys.argv) > 3 else None

    ctrl = AutoController()
    try:
        if script_path and Path(script_path).exists():
            with open(script_path, "r", encoding="utf-8") as f:
                steps = json.load(f)

            print(f"Executing {len(steps)} steps...")
            ctrl.launch(exe_path)

            for i, step in enumerate(steps):
                action = step.get("action", "click")
                target = step.get("target", "")
                value = step.get("value", "")
                by = step.get("by", "text")
                print(f"  [{i+1}] {action} -> {target}", end=" ")

                if action == "click":
                    ok = ctrl.click(target, by=by)
                elif action == "input":
                    ok = ctrl.type_text(target, value, by=by)
                elif action == "select":
                    ok = ctrl.select(target, value, by=by)
                elif action == "wait":
                    ctrl.wait(seconds=float(value or 1))
                    ok = True
                elif action == "keys":
                    ctrl.send_keys(value)
                    ok = True
                else:
                    ok = False

                print("+" if ok else "-")
                time.sleep(settings.action_delay)
        else:
            print(f"Launching: {exe_path}")
            ctrl.launch(exe_path)
            print("App launched.")

        report = ctrl.report()
        print(f"\nReport: {report['steps_total']} steps, "
              f"{report['success']} OK, {report['failures']} FAIL")

    finally:
        ctrl.close()


def cmd_explore():
    """Interactive UI probe"""
    title = sys.argv[2] if len(sys.argv) > 2 else None
    from inspector.explorer import UIExplorer

    explorer = UIExplorer()

    if title:
        print(f"Exploring: {title}")
        tree = explorer.dump_tree(title=title)
        print(json.dumps(tree, indent=2, ensure_ascii=False)[:5000])
    else:
        print("Desktop windows:")
        windows = explorer.list_windows()
        for w in windows:
            print(
                f"  [handle={w['handle']}] {w['title']:40s} "
                f"class={w['class']:20s} "
                f"{w['rect']['width']}x{w['rect']['height']}"
            )

        search = input("\nEnter window title to probe (or Enter to exit): ").strip()
        if search:
            tree = explorer.dump_tree(title=search)
            print(json.dumps(tree, indent=2, ensure_ascii=False)[:5000])

    print("\nExport:")
    path = explorer.export_tree(title=title)
    print(f"  {path}")


def cmd_inspect():
    """Launch app and inspect its controls"""
    if len(sys.argv) < 3:
        print("Usage: python main.py inspect <exe_path>")
        return

    exe_path = sys.argv[2]
    ctrl = AutoController()

    try:
        print(f"Launching: {exe_path}")
        ctrl.launch(exe_path, wait_seconds=2)

        from inspector.explorer import UIExplorer
        explorer = UIExplorer()
        title = ctrl.state.window_title

        print(f"\n{'='*55}")
        print(f"  Target window: {title}")
        print(f"{'='*55}")

        tree = explorer.dump_tree(title=title, max_depth=6)

        def extract_controls(node, path="", depth=0):
            """Recursively extract meaningful controls"""
            lines = []
            indent = "  " * depth
            name = node.get("name", "") or node.get("text", "")
            ctype = node.get("type", "")
            aid = node.get("auto_id", "")
            rect = node.get("rect", {})

            if ctype in (
                "Button", "Edit", "ComboBox", "CheckBox",
                "MenuItem", "TabItem", "List", "Tree",
                "Hyperlink", "RadioButton", "Spinner",
                "ScrollBar", "Slider", "StatusBar",
            ):
                aid_str = f" auto_id={aid}" if aid else ""
                text_str = f" text=\"{name[:30]}\"" if name else ""
                size_str = f" [{rect.get('w',0)}x{rect.get('h',0)}]" if rect else ""
                lines.append(f"{indent}  {ctype:12s}{aid_str}{text_str}{size_str}")
            elif ctype == "Window" and name:
                lines.append(f"{indent}  [{ctype}] {name}")

            for child in node.get("children", []):
                sub = extract_controls(child, path, depth + 1)
                if sub:
                    lines.extend(sub)
            return lines

        controls = extract_controls({"children": tree})
        if controls:
            print("\n  Key controls:\n")
            for line in controls:
                print(f"  {line}")
        else:
            print("\n  (No interactive controls found, showing raw tree)")
            print(json.dumps(tree, indent=2, ensure_ascii=False)[:3000])

        path = explorer.export_tree(title=title)
        print(f"\n  Full tree exported: {path}")
        print("\n  Tip: Use auto_id / name / control_type from the JSON to script automation.")

    finally:
        ctrl.close()


def cmd_script():
    """Execute a Python script file"""
    if len(sys.argv) < 3:
        print("Usage: python main.py script <script.py>")
        return

    script_path = sys.argv[2]
    script_file = Path(script_path)

    if not script_file.exists():
        print(f"Script not found: {script_path}")
        return

    ctrl = AutoController()

    script_globals = {
        "__file__": str(script_file),
        "auto": ctrl,
        "ctrl": ctrl,
        "app": ctrl.driver,
        "Actions": __import__("automation.actions", fromlist=["Actions"]).Actions,
        "By": __import__("automation.locator", fromlist=["By"]).By,
        "Workflow": Workflow,
        "logger": logger,
    }

    print(f"Running script: {script_path}")
    try:
        exec(script_file.read_text(encoding="utf-8"), script_globals)
        report = ctrl.report()
        print(f"\nReport: {report['steps_total']} steps, "
              f"{report['success']} OK, {report['failures']} FAIL")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ctrl.close()


def cmd_goal():
    """AI-driven natural language goal execution"""
    if len(sys.argv) < 3:
        print("Usage: python main.py goal \"<desc>\" [exe_path]")
        return

    goal = sys.argv[2]
    app_path = sys.argv[3] if len(sys.argv) > 3 else None

    logger.info(f"Goal: {goal}")
    ctrl = AutoController()

    try:
        success = ctrl.execute_goal(goal, app_path)
        report = ctrl.report()
        print(f"\nReport: {report['steps_total']} steps, "
              f"{report['success']} OK, {report['failures']} FAIL")
        sys.exit(0 if success else 1)
    finally:
        ctrl.close()


def cmd_record():
    """Record window state changes over time"""
    if len(sys.argv) < 3:
        print("Usage: python main.py record <exe_path> [duration]")
        return

    exe_path = sys.argv[2]
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    from inspector.explorer import UIExplorer
    ctrl = AutoController()

    try:
        print(f"Launching: {exe_path}")
        ctrl.launch(exe_path, wait_seconds=2)

        explorer = UIExplorer()
        print(f"Recording for {duration}s...")
        actions = explorer.record_actions(duration)
        print(f"Done: {len(actions)} snapshots")
        for a in actions:
            print(f"  [{a['seq']}] {a['active_title']}")
    finally:
        ctrl.close()


if __name__ == "__main__":
    main()
