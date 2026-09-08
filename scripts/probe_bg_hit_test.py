"""跨平台验证后台点击命中嵌套子窗口，不调用真实 Win32。"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

source = Path(__file__).resolve().parents[1] / 'automation/background.py'
tree = ast.parse(source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == '_deepest_child']


class HitTest(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.convert = Mock(side_effect=lambda hwnd, x, y: (x - hwnd, y - hwnd))
        ns = dict(user32=self.api, _screen_to_client=self.convert,
                  wintypes=SimpleNamespace(POINT=lambda x, y: (x, y)),
                  CWP_SKIPINVISIBLE=1, CWP_SKIPDISABLED=2, CWP_SKIPTRANSPARENT=4)
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), ns)
        self.hit = ns['_deepest_child']

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
