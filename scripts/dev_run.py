#!/usr/bin/env python3
"""AutoDrive 开发调试启动器：真窗口 + 热键直达页面 + QSS 保存即热重载。

用法:
  python scripts/dev_run.py [page_id] [--theme light] [--demo] [--perf] [--offscreen]

参数:
  page_id     启动后直达该页（如 ebs-dataflow / report），无效则留在主页
  --theme X   初始主题（dark 默认 / light）
  --demo      启动即跑演示诊断并跳 ai-diagn 页
  --perf      打印 goPage / 主题切换耗时（dev 工具允许 stdout）
  --offscreen 离屏运行（无窗口，适合无显示器环境自检）

热键（全局生效，与焦点无关）:
  T    切换 深色⇄浅色 主题
  R    手动重载 ui/theme.qss（与文件 watcher 同一函数）
  F    一键演示诊断 + 跳 ai-diagn 页
  1..9 跳 PAGE_ORDER 前 9 页；0 跳第 10 页
  Esc  回主页

QSS 热重载：编辑 ui/theme.qss 保存即生效（QFileSystemWatcher）。
"""

import os
import sys
import time
from pathlib import Path

# 管道输出时 stdout 编码在启动时已定（Windows 默认 cp1252），此处强制 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_QSS_FILE = ROOT / "ui" / "theme.qss"


def _parse_args():
    page = None
    theme = None
    demo = perf = offscreen = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--theme":
            if i + 1 < len(args):
                theme = args[i + 1]
                i += 1
        elif a.startswith("--theme="):
            theme = a.split("=", 1)[1]
        elif a == "--demo":
            demo = True
        elif a == "--perf":
            perf = True
        elif a == "--offscreen":
            offscreen = True
        elif a.startswith("-"):
            print(f"[dev_run] 未知参数：{a}")
        else:
            page = a
        i += 1
    if theme not in (None, "dark", "light"):
        print(f"[dev_run] 无效主题：{theme}（仅 dark/light）")
        theme = None
    return page, theme, demo, perf, offscreen


def main():
    page, theme, demo, perf, offscreen = _parse_args()
    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QFileSystemWatcher, Qt
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import QApplication

    from ui import theme_qss
    from ui.appshell import PAGE_ORDER
    from ui.wizard import MainWindow

    app = QApplication(sys.argv)

    perf_t = {"t0": 0.0}

    def _p(label, ms):
        if perf:
            print(f"[perf] {label}: {ms:.1f} ms")

    w = MainWindow()
    w.show()

    # ── 初始参数应用 ────────────────────────────
    if theme in ("dark", "light"):
        w.theme.set_theme(theme)
    if page:
        if page in PAGE_ORDER:
            w.shell.goPage(page)
        else:
            w.shell.toast(f"未知页面：{page}（共 {len(PAGE_ORDER)} 页）", "crit")

    # ── QSS 热重载 ─────────────────────────────
    _watcher = QFileSystemWatcher([str(_QSS_FILE)])

    def _reload_qss(manual: bool = True):
        try:
            theme_qss.reload_template()
            w.theme.apply()
            if manual:
                w.shell.toast("QSS 已热重载", "ok")
            print("[dev_run] QSS 已重载")
        except Exception as e:  # noqa: BLE001
            print(f"[dev_run] QSS 重载失败：{e}")
            w.shell.toast("QSS 重载失败", "crit")

    def _on_qss_changed(_path):
        # Qt 已知行为：watcher 触发一次后需重新 addPath，否则后续不再生效
        _reload_qss(manual=True)
        _watcher.addPath(str(_QSS_FILE))

    _watcher.fileChanged.connect(_on_qss_changed)

    # ── 热键 ───────────────────────────────────
    def _shortcut(key, fn):
        s = QShortcut(QKeySequence(key), w)
        s.setContext(Qt.ApplicationShortcut)
        s.activated.connect(fn)

    def _toggle_theme():
        perf_t["t0"] = time.perf_counter()
        w.theme.set_theme("light" if w.theme.resolved == "dark" else "dark")

    def _run_demo():
        w.shell.goPage("ai-diagn")
        w._run_demo_diagnosis("演示诊断")

    _shortcut("T", _toggle_theme)
    _shortcut("R", lambda: _reload_qss(manual=True))
    _shortcut("F", _run_demo)
    _shortcut("Esc", lambda: w.shell.goPage("home"))
    for i, pid in enumerate(PAGE_ORDER[:10]):
        key = str(i + 1) if i < 9 else "0"
        _shortcut(key, lambda _p=pid: w.shell.goPage(_p))

    # ── --perf 计时 ────────────────────────────
    if perf:
        w.theme.changed.connect(
            lambda m: _p(f"theme apply → {m}", (time.perf_counter() - perf_t["t0"]) * 1000))
        orig = w.shell.goPage

        def _timed_go(pid):
            t0 = time.perf_counter()
            orig(pid)
            _p(f"goPage({pid}) 页面数={len(w.pages)}", (time.perf_counter() - t0) * 1000)

        w.shell.goPage = _timed_go

    if demo:
        _run_demo()

    print(f"[dev_run] 启动完成：theme={w.theme.resolved} accent={w.theme.accent} "
          f"已建页={len(w.pages)}/{len(PAGE_ORDER)}  page={page or 'home'}")
    print("[dev_run] 热键：T 主题 / R 重载QSS / F 演示 / 1-9,0 跳页 / Esc 主页。编辑 ui/theme.qss 保存即生效。")

    app.exec()


if __name__ == "__main__":
    main()
