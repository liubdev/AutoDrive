"""跨平台验证后台点击命中嵌套子窗口，不调用真实 Win32。"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

source = Path(__file__).resolve().parents[1] / 'automation/background.py'
tree = ast.parse(source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {'_deepest_child', 'click_at'}]


class HitTest(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.convert = Mock(side_effect=lambda hwnd, x, y: (x - hwnd, y - hwnd))
        ns = dict(user32=self.api, _screen_to_client=self.convert,
                  wintypes=SimpleNamespace(POINT=lambda x, y: (x, y)),
                  CWP_SKIPINVISIBLE=1, CWP_SKIPDISABLED=2, CWP_SKIPTRANSPARENT=4)
        ns.update(logger=Mock(), WM_MOUSEMOVE=0x200, WM_LBUTTONDOWN=0x201,
                  WM_LBUTTONUP=0x202, WM_LBUTTONDBLCLK=0x203, MK_LBUTTON=1)
        self.ns = ns
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), ns)
        self.hit = ns['_deepest_child']

    def test_double_click_message_sequence_and_same_target(self):
        self.ns['_deepest_child'] = Mock(return_value=30)
        self.api.IsWindow.return_value = True
        self.assertTrue(self.ns['click_at'](10, 100, 200, double=True))
        calls = self.api.SendMessageW.call_args_list
        self.assertEqual([c.args[1] for c in calls], [0x200, 0x201, 0x202, 0x203, 0x202])
        self.assertTrue(all(c.args[0] == 30 for c in calls))
        self.ns['_deepest_child'].assert_called_once()

    def test_single_click_remains_single(self):
        self.ns['_deepest_child'] = Mock(return_value=30)
        self.assertTrue(self.ns['click_at'](10, 100, 200))
        self.assertEqual([c.args[1] for c in self.api.SendMessageW.call_args_list],
                         [0x200, 0x201, 0x202])

    def test_double_click_stops_if_target_destroyed(self):
        self.ns['_deepest_child'] = Mock(return_value=30)
        self.api.IsWindow.return_value = False
        self.assertFalse(self.ns['click_at'](10, 100, 200, double=True))
        self.assertEqual(self.api.SendMessageW.call_count, 3)

    def test_nested_child_and_local_coordinates(self):
        self.api.ChildWindowFromPointEx.side_effect = [20, 30, 30]
        self.assertEqual(self.hit(10, 100, 200), 30)
        self.assertEqual([c.args for c in self.api.ChildWindowFromPointEx.call_args_list],
                         [(10, (90, 190), 7), (20, (80, 180), 7), (30, (70, 170), 7)])

    def test_self_is_leaf(self):
        self.api.ChildWindowFromPointEx.return_value = 10
        self.assertEqual(self.hit(10, 100, 200), 10)

    def test_no_hit_does_not_fall_back_to_parent(self):
        self.api.ChildWindowFromPointEx.side_effect = [20, 0]
        self.assertEqual(self.hit(10, 100, 200), 0)

    def test_cycle_stops(self):
        self.api.ChildWindowFromPointEx.side_effect = [20, 10]
        self.assertEqual(self.hit(10, 100, 200), 0)


if __name__ == '__main__':
    unittest.main()
