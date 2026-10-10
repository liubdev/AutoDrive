"""Preview the embedded reference manual without starting DTS or AI requests."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QApplication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    parser.add_argument("--screenshot", type=Path, help="Capture the preview and exit")
    args = parser.parse_args()
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")

    from ui.pages.ai_diag import AiDiagPage
    from ui.report import build_demo_ai_report, build_demo_report
    from ui.theme import ThemeManager

    theme = ThemeManager(app)
    theme.theme = args.theme
    theme.apply()
    page = AiDiagPage()
    page.setWindowTitle("AutoDrive - HTML 手册预览（演示数据）")
    page.resize(1280, 960)
    page.set_report(build_demo_report())
    report = build_demo_ai_report()
    page.show_report(report)
    page.render_steps(report)
    page.show()

    def scroll_to_manual():
        page._scroll.ensureWidgetVisible(page._result_views, 0, 0)

    def capture():
        scroll_to_manual()
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        if not page.grab().save(str(args.screenshot)):
            app.exit(1)
            return
        app.exit(0)

    def loaded(ok):
        if not ok:
            app.exit(1)
            return
        QTimer.singleShot(0, scroll_to_manual)
        if args.screenshot:
            QTimer.singleShot(1200, capture)

    def open_manual():
        page._result_views._buttons.button(1).click()
        view = page._result_views._manual._view
        if view is None:
            if args.screenshot:
                app.exit(1)
            return
        view.loadFinished.connect(loaded)

    QTimer.singleShot(0, open_manual)
    if args.screenshot:
        QTimer.singleShot(30000, lambda: app.exit(1))
    code = app.exec()
    page.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
