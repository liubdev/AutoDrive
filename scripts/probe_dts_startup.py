"""跨平台逻辑回归：用进程/UI 桩验证启动失败关闭和点击不重放，不操作真实 DTS。"""
import ast
import logging
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 本探针不需要安装 Windows UIA 或 psutil，不执行任何真实进程操作。
psutil = SimpleNamespace(NoSuchProcess=type('NoSuchProcess', (Exception,), {}),
                         AccessDenied=type('AccessDenied', (Exception,), {}),
                         process_iter=Mock(), wait_procs=Mock())
with patch.dict(sys.modules, psutil=psutil):
    from automation.processes import stop_executable

# 仅载入真实 DtsApp 的方法体，隔离 Windows 专用导入/基类初始化。
tree = ast.parse((ROOT / 'automation/apps/dts.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DtsApp')
cls.bases = []
cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef)
            and n.name in {'one_click_enter', 'enter_system', 'restart_for_diagnosis', '_wait_ready', 'confirm',
                           '_wait_for_dts_window', '_home_anchor', '_ready_control', '_probe_startup'}]
clock = SimpleNamespace(monotonic=Mock(), sleep=Mock())
ns = {'time': clock, 'logger': logging.getLogger('probe')}
exec(compile(ast.Module(body=[cls], type_ignores=[]), 'dts.py', 'exec'), ns)
DtsApp = ns['DtsApp']


class StartupTests(unittest.TestCase):
    def setUp(self):
        clock.monotonic.side_effect = None
        clock.monotonic.return_value = 0
        clock.sleep.reset_mock()
        clock.sleep.side_effect = None
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exe = Path(self.temp.name) / 'DTS650.exe'
        self.exe.touch()
        psutil.process_iter.reset_mock()
        psutil.wait_procs.reset_mock()
        psutil.wait_procs.return_value = ([], [])

    def process(self, path, pid):
        return SimpleNamespace(info={'name': 'DTS650.exe'}, exe=Mock(return_value=str(path.resolve())),
                               pid=pid, kill=Mock())

    def test_only_configured_installation_and_all_instances(self):
        a, b = self.process(self.exe, 1), self.process(self.exe, 2)
        other = self.process(Path(self.temp.name) / 'other/DTS650.exe', 3)
        psutil.process_iter.return_value = [a, b, other]
        stop_executable(str(self.exe))
        a.kill.assert_called_once()
        b.kill.assert_called_once()
        other.kill.assert_not_called()
        psutil.wait_procs.assert_called_once_with([a, b], timeout=10)

    def test_exit_timeout_blocks_restart(self):
        p = self.process(self.exe, 1)
        psutil.process_iter.return_value = [p]
        psutil.wait_procs.return_value = ([], [p])
        app = DtsApp()
        app.APP_EXE = str(self.exe)
        app.ensure_running = Mock()
        app.disconnect = Mock()
        with self.assertRaises(RuntimeError):
            app.restart_for_diagnosis()
        app.ensure_running.assert_not_called()

    def test_permission_failure_blocks_cleanup(self):
        p = self.process(self.exe, 1)
        p.exe.side_effect = psutil.AccessDenied()
        psutil.process_iter.return_value = [p]
        with self.assertRaises(RuntimeError):
            stop_executable(str(self.exe))
        p.kill.assert_not_called()

    def test_no_process_starts_fresh(self):
        psutil.process_iter.return_value = []
        app = DtsApp()
        app.APP_EXE = str(self.exe)
        app.disconnect = Mock()
        app.ensure_running = Mock(return_value=True)
        self.assertTrue(app.restart_for_diagnosis())
        app.disconnect.assert_called_once()
        app.ensure_running.assert_called_once_with(30, fresh=True)

    def test_navigation_timeout_does_not_repeat_click(self):
        app = DtsApp()
        app._reconnect_main = Mock(return_value=True)
        app._ready_control = Mock(return_value=None)
        app._wait_ready = Mock(side_effect=[object(), None])
        app._click_image_btn = Mock(return_value=True)
        self.assertFalse(app.one_click_enter())
        app._click_image_btn.assert_called_once()

    def test_existing_target_prevents_click(self):
        app = DtsApp()
        app._reconnect_main = Mock(return_value=True)
        app._ready_control = Mock(return_value=object())
        app._click_below_text = Mock()
        self.assertTrue(app.enter_system())
        app._click_below_text.assert_not_called()

    def navigation_app(self, target_after=None, source_until=None, disabled_target_after=None):
        app = DtsApp()
        ticks = [0.0]
        clock.monotonic.side_effect = lambda: ticks[0]
        clock.sleep.side_effect = lambda seconds: ticks.__setitem__(0, ticks[0] + seconds)
        app._reconnect_main = Mock(return_value=True)
        rect = SimpleNamespace(left=20, bottom=89, width=lambda: 1880, height=lambda: 38)
        parent = SimpleNamespace(handle=456, is_visible=lambda: True, is_enabled=lambda: True)
        anchor = SimpleNamespace(handle=123, rectangle=lambda: rect, parent=lambda: parent)
        app.click_at = Mock(return_value=True)
        def ready(**selector):
            if selector['auto_id'] == '1185':
                return anchor if source_until is None or ticks[0] < source_until else None
            if target_after is not None and app.click_at.call_count >= target_after:
                return object()
            if (disabled_target_after is not None and ticks[0] >= disabled_target_after
                    and not selector.get('require_enabled', True)):
                return object()
            return None
        app._ready_control = Mock(side_effect=ready)
        return app

    def test_enter_system_retries_after_anchor_handle_changes(self):
        app = self.navigation_app(target_after=2)
        original = app._ready_control.side_effect
        def rebuilt(**selector):
            ctrl = original(**selector)
            if ctrl is not None and selector['auto_id'] == '1185':
                ctrl.handle += 1
            return ctrl
        app._ready_control.side_effect = rebuilt
        self.assertTrue(app.enter_system(timeout=5))
        self.assertEqual(app.click_at.call_count, 2)

    def test_enter_system_does_not_click_disabled_page(self):
        app = self.navigation_app()
        original = app._ready_control.side_effect
        def disabled(**selector):
            ctrl = original(**selector)
            if ctrl is not None and selector['auto_id'] == '1185':
                ctrl.parent().is_enabled = lambda: False
            return ctrl
        app._ready_control.side_effect = disabled
        self.assertFalse(app.enter_system(timeout=2))
        app.click_at.assert_not_called()

    def test_enter_system_retries_missed_click(self):
        app = self.navigation_app(target_after=2)
        self.assertTrue(app.enter_system(timeout=5))
        self.assertEqual(app.click_at.call_count, 2)

    def test_enter_system_stops_clicking_on_success(self):
        app = self.navigation_app(target_after=1)
        self.assertTrue(app.enter_system(timeout=5))
        app.click_at.assert_called_once_with(144, 152)

    def test_enter_system_retry_cap(self):
        app = self.navigation_app()
        self.assertFalse(app.enter_system(timeout=6))
        self.assertEqual(app.click_at.call_count, 3)

    def test_enter_system_no_retry_after_source_disappears(self):
        app = self.navigation_app(source_until=0.5)
        self.assertFalse(app.enter_system(timeout=4))
        app.click_at.assert_called_once()

    def test_enter_system_no_retry_when_target_initializing(self):
        app = self.navigation_app(disabled_target_after=0.5)
        self.assertFalse(app.enter_system(timeout=4))
        app.click_at.assert_called_once()

    def test_enter_system_short_timeout_limits_retries(self):
        app = self.navigation_app()
        self.assertFalse(app.enter_system(timeout=1))
        app.click_at.assert_called_once()

    def test_missing_confirm_skips_without_sleep(self):
        app = DtsApp()
        app._probe_startup = Mock(return_value=("home", None))
        app.click_ctrl = Mock()
        self.assertTrue(app.confirm())
        app.click_ctrl.assert_not_called()
        clock.sleep.assert_not_called()

    def test_startup_accepts_home_without_confirm(self):
        app = DtsApp()
        app._probe_startup = Mock(return_value=("home", None))
        self.assertTrue(app._wait_for_dts_window())
        clock.sleep.assert_not_called()

    def test_delayed_confirm_is_clicked_once_until_home(self):
        app = DtsApp()
        btn = object()
        app._probe_startup = Mock(side_effect=[(None, None), ("confirm", btn),
                                              ("confirm", btn), ("home", None)])
        app.click_ctrl = Mock(return_value=True)
        self.assertTrue(app.confirm())
        app.click_ctrl.assert_called_once_with(btn)

    def test_unknown_page_is_not_skipped(self):
        app = DtsApp()
        app._probe_startup = Mock(return_value=(None, None))
        app.click_ctrl = Mock()
        clock.monotonic.side_effect = [0, 0, 2]
        self.assertFalse(app.confirm(timeout=1))
        app.click_ctrl.assert_not_called()

    def test_disabled_paging_button_is_valid_anchor(self):
        app = DtsApp()
        button = Mock()
        button.exists.return_value = True
        button.is_visible.return_value = True
        button.is_enabled.return_value = False
        app.window = Mock()
        app.window.child_window.return_value = button
        self.assertIs(app._home_anchor(), button)
        self.assertIsNone(app._ready_control(auto_id="1013", control_type="Button"))

    def test_probe_prefers_confirm_over_home_and_filters_pid(self):
        app = DtsApp()
        app._pid = 42
        main = SimpleNamespace(class_name="CDTS650MainClass", name="DTS650", handle=1, process_id=42)
        dialog = SimpleNamespace(class_name="#32770", name="", handle=2, process_id=42,
                                 children=lambda: [SimpleNamespace(name="确认")])
        app._connect_by_handle = Mock(return_value=True)
        btn = object()
        app._ready_control = Mock(return_value=btn)
        app._apply_window_hiding = Mock()
        finder = Mock(return_value=[main, dialog])
        with patch.dict(ns, find_elements=finder):
            self.assertEqual(app._probe_startup(), ("confirm", btn))
        finder.assert_called_once_with(backend="uia", top_level_only=True, process=42)
        app._connect_by_handle.assert_called_once_with(2, 42)

    def test_wait_returns_immediately_when_ready(self):
        app = DtsApp()
        ctrl = object()
        app._ready_control = Mock(return_value=ctrl)
        clock.monotonic.side_effect = [0, 0]
        clock.sleep.reset_mock()
        self.assertIs(app._wait_ready(auto_id='1'), ctrl)
        clock.sleep.assert_not_called()


if __name__ == '__main__':
    with patch.dict(sys.modules, psutil=psutil):
        unittest.main()
