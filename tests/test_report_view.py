"""HTML reader integration checks; no DTS connection or vehicle operations."""

import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from ui.report_view import ManualView, ReportViews, manual_path


class ReportViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        for widget in self.app.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def wait_until(self, predicate, timeout=20):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(25)
        self.assertTrue(predicate(), "Timed out waiting for the HTML reader")

    def test_bundled_and_frozen_paths(self):
        content = manual_path().read_text(encoding="utf-8")
        self.assertIn("MD1CS089", content)
        self.assertIn("<svg", content)
        self.assertIn("测量速查表", content)
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", str(Path("installed") / "AutoDrive.exe")
        ):
            self.assertEqual(
                manual_path(),
                Path("installed").resolve() / "ui/assets/manuals/md1cs089_v6.html",
            )

    def test_missing_file_keeps_retry_available(self):
        reader = ManualView()
        with TemporaryDirectory() as directory, patch(
            "ui.report_view.manual_path", return_value=Path(directory) / "missing.html"
        ):
            reader.ensure_loaded()
        self.assertIsNone(reader._view)
        self.assertIn("缺失", reader._status.text())
        self.assertTrue(reader._retry.isEnabled())

    def test_real_html_load_switch_and_zoom(self):
        content = QLabel("Actual diagnosis result")
        tabs = ReportViews(content)
        tabs.resize(1100, 780)
        tabs.show()
        self.assertIsNone(tabs._manual._view)
        tabs._buttons.button(1).click()
        reader = tabs._manual
        self.wait_until(lambda: not reader._loading)
        self.assertIsNotNone(reader._view, reader._status.text())
        self.assertFalse(reader._view.isHidden(), reader._status.text())
        text = []
        reader._view.page().toPlainText(text.append)
        self.wait_until(lambda: bool(text))
        self.assertIn("MD1CS089", text[0])
        self.assertIn("测量速查表", text[0])
        reader._zoom_in.click()
        self.assertAlmostEqual(reader._view.zoomFactor(), 1.1)
        reader._zoom_reset.click()
        self.assertAlmostEqual(reader._view.zoomFactor(), 1.0)
        browser = reader._view
        tabs.show_result()
        self.assertFalse(content.isHidden())
        tabs._buttons.button(1).click()
        self.assertIs(reader._view, browser)
        self.assertEqual(content.text(), "Actual diagnosis result")

    def test_ai_reset_and_history_details(self):
        from ui.pages.ai_diag import AiDiagPage
        from ui.pages.report import ReportListPage
        from ui.report import ReportMeta

        page = AiDiagPage()
        self.assertIsNone(page._result_views._manual._view)
        page.show_report({"diagnosisList": [{"faultPoint": "Test fault"}]})
        self.assertIn("Test fault", page._report_texts())
        with patch.object(page._result_views._manual, "ensure_loaded"):
            page._result_views._buttons.button(1).click()
            page.reset()
        self.assertTrue(page._result_views._buttons.button(0).isChecked())
        self.assertIsNone(page._result)

        history = ReportListPage()
        history._open_paper(ReportMeta(time="2026-10-10 12:00"), demo=True)
        self.assertEqual(len(history.findChildren(ReportViews)), 1)
        history._open_paper(ReportMeta(time="2026-10-10 13:00"), demo=True)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertEqual(len(history.findChildren(ReportViews)), 1)


if __name__ == "__main__":
    unittest.main()
