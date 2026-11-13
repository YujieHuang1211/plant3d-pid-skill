"""界区符号（QMZ Battery Limit Style）与管线的相对位置：进口旗尖对着管线起点，出口旗的平边贴管线终点，管线不得伸进旗内或穿过旗。"""
import unittest

import _util  # noqa: F401

import lint_specs

CAT = {lint_specs.BL_STYLE: {'bbox': [-10, -3, 10, 3], 'att': []}}
BL = lint_specs.BL_STYLE


def lint(items, warns=None):
    errs = []
    warns = [] if warns is None else warns
    lint_specs.lint_sheet('P&ID-101', items, CAT, {i['id'] for i in items if i.get('id')}, errs, warns)
    return errs


def sheet(pts, at, rot, ctx, extra=()):
    return [{'k': 'line', 'id': 'L1', 'pts': pts},
            {'k': 'asset', 'id': 'BL-1', 'style': BL, 'at': at, 'rot': rot},
            {'k': 'connect', 'line': 'L1', 'asset': 'BL-1', 'ctx': ctx}, *extra]


class BatteryLimit(unittest.TestCase):
    def test_outlet_flag_beyond_line_end_ok(self):
        self.assertEqual(lint(sheet([[100, 50], [150, 50]], [160, 50], 0, 'end')), [])

    def test_outlet_flag_centred_on_line_end_is_error(self):
        errs = lint(sheet([[100, 50], [150, 50]], [150, 50], 0, 'end'))
        self.assertTrue(any('界区符号' in e for e in errs), errs)

    def test_downward_outlet_ok_and_wrong(self):
        self.assertEqual(lint(sheet([[100, 80], [100, 50]], [100, 40], 270, 'end')), [])
        self.assertTrue(lint(sheet([[100, 80], [100, 50]], [100, 50], 270, 'end')))

    def test_inlet_tip_at_line_start_ok(self):
        self.assertEqual(lint(sheet([[100, 50], [150, 50]], [90, 50], 0, 'start')), [])

    def test_inlet_flag_centred_on_line_start_is_error(self):
        self.assertTrue(lint(sheet([[100, 50], [150, 50]], [100, 50], 0, 'start')))

    def test_small_offset_is_warning_not_error(self):
        warns = []
        self.assertEqual(lint(sheet([[100, 50], [150, 50]], [158, 50], 0, 'end'), warns), [])
        self.assertTrue(any('W-BL-END' in w for w in warns), warns)

    def test_other_line_crossing_flag_is_error(self):
        other = [{'k': 'line', 'id': 'L2', 'pts': [[155, 40], [155, 60]]}]
        errs = lint(sheet([[100, 50], [150, 50]], [160, 50], 0, 'end', other))
        self.assertTrue(any('穿过界区符号' in e for e in errs), errs)

    def test_other_line_beside_flag_ok(self):
        other = [{'k': 'line', 'id': 'L2', 'pts': [[140, 40], [140, 60]]}]
        self.assertEqual(lint(sheet([[100, 50], [150, 50]], [160, 50], 0, 'end', other)), [])


if __name__ == '__main__':
    unittest.main()
