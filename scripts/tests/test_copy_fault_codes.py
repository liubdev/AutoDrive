"""Exercise fault-code copying without a live DTS process or system clipboard."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2] / "automation/apps/dts.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DtsApp")
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "copy_all_rows")


class CopyTests(unittest.TestCase):
    def run_copy(self, *, stale=False, click_ok=True, busy=0):
        state = SimpleNamespace(seq=1, row=0, closed=False, clock=0, busy=busy, opens=0, closes=0)
        def sleep(seconds):
            state.clock += seconds
        def open_clipboard():
            if state.busy:
                state.busy -= 1
                raise OSError("busy")
            state.opens += 1
        def close_clipboard():
            state.closes += 1
        clipboard = SimpleNamespace(
            CF_UNICODETEXT=13, OpenClipboard=open_clipboard,
            CloseClipboard=close_clipboard, IsClipboardFormatAvailable=lambda _: True,
            GetClipboardData=lambda _: ["P0001", "P0002", "P0002"][state.row - 1],
        )
        button = SimpleNamespace(exists=lambda **_: True, is_enabled=lambda: True)
        ok = SimpleNamespace(exists=lambda **_: True, is_enabled=lambda: True, handle=123)
        ok.wrapper_object = lambda: ok
        def click(control):
            if not click_ok:
                return False
            if control is button:
                state.row += 1
                state.closed = False
                if not stale:
                    state.seq += 1
            else:
                state.closed = True
            return True
        app = SimpleNamespace(
            _focus_list=lambda: object(), send_keys_to=lambda *_: None, click_ctrl=click,
            window=SimpleNamespace(child_window=lambda **kw: button if kw["auto_id"] == "1011" else ok),
        )
        namespace = dict(
            settings=SimpleNamespace(dts_poll_interval=0.1, dts_page_settle=0.25, dts_copy_timeout=1),
            time=SimpleNamespace(sleep=sleep, monotonic=lambda: state.clock),
            logger=logging.getLogger("test"),
        )
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), "exec"), namespace)
        import ctypes
        with patch.dict("sys.modules", {"win32clipboard": clipboard, "win32gui": SimpleNamespace(
            IsWindow=lambda _: not state.closed, IsWindowVisible=lambda _: not state.closed)}), patch.object(
            ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetClipboardSequenceNumber=lambda: state.seq)), create=True
        ):
            result = namespace["copy_all_rows"](app, "1011")
        self.assertEqual(state.opens, state.closes)
        return result, state

    def test_success_and_duplicate_end(self):
        result, state = self.run_copy()
        self.assertEqual(result, ["P0001", "P0002"])
        self.assertLess(state.clock, 2)

    def test_busy_clipboard_retries(self):
        result, _ = self.run_copy(busy=2)
        self.assertEqual(result, ["P0001", "P0002"])

    def test_stale_clipboard_fails(self):
        with self.assertRaisesRegex(RuntimeError, "超时"):
            self.run_copy(stale=True)

    def test_failed_click_stops(self):
        with self.assertRaisesRegex(RuntimeError, "点击失败"):
            self.run_copy(click_ok=False)


if __name__ == "__main__":
    unittest.main()
