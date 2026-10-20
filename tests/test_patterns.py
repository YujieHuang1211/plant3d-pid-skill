"""版面模块：气源支路、控制回路。生成的 spec 必须通过 lint，几何符合约定。"""
import json
import unittest

import _util
from _util import ROOT

import lint_specs
import patterns
import pidlib

CAT = json.loads((ROOT / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))


def model():
    inl = lambda t, typ, **kw: dict(tag=t, type=typ, desc=t, spec='', src='C', **kw)
    return {'meta': {'project': 'x', 'rev': 'R0', 'date': '2026-10-20'}, 'conventions': {},
            'boundary': [{'id': 'BL-N2', 'dir': 'in', 'desc': 'N2', 'cond': '', 'by': '甲方', 'src': 'C'}],
            'equipment': [], 'tees': [], 'lines': [], 'signals': [], 'interlocks': [], 'modes': [],
            'inline': [inl('HV-101', 'ball_valve'), inl('FL-101', 'filter'), inl('PCV-101', 'regulator'),
                       inl('XV-101', 'on_off_valve', fail='FC'), inl('FIC-101', 'mfc'), inl('CK-101', 'check_valve')],
            'instruments': [{'tag': 'PI-101', 'desc': 'PI', 'src': 'C', 'range': '0-1'}, {'tag': 'FIC-101', 'src': 'C', 'desc': 'x'}],
            'sheets': [{'no': 'P&ID-101', 'title': 't'}]}


def build():
    pidlib.use_model(model())
    s = pidlib.Sheet('P&ID-101')
    r = patterns.gas_branch(s, 200, 'N2', '0101', bl='BL-N2', label='N₂ 气源', hv='HV-101', fl='FL-101', pcv='PCV-101', pi='PI-101',
                            xv='XV-101', mfc='FIC-101', ck='CK-101', x_end=300)
    return s, r


class GasBranch(unittest.TestCase):
    def test_all_components_placed_and_lint_clean(self):
        s, r = build()
        tags = {i['id'] for i in s.items if i.get('id')}
        for t in ('BL-N2', 'HV-101', 'FL-101', 'PCV-101', 'PI-101', 'XV-101', 'FIC-101', 'CK-101'):
            self.assertIn(t, tags)
        errs, warns = [], []
        lint_specs.lint_sheet('P&ID-101', s.items, CAT, {i['id'] for i in s.items if i.get('id')}, errs, warns)
        self.assertEqual(errs, [])
        self.assertEqual(r['no'], 'N2-0101-6-S1')

    def test_optional_components_are_skipped(self):
        pidlib.use_model(model())
        s = pidlib.Sheet('P&ID-101')
        patterns.gas_branch(s, 200, 'N2', '0101', bl='BL-N2', hv='HV-101', ck='CK-101', x_end=300)
        tags = {i['id'] for i in s.items if i.get('id')}
        self.assertEqual(tags, {'LN2', 'BL-N2', 'HV-101', 'CK-101'})

    def test_column_override(self):
        pidlib.use_model(model())
        s = pidlib.Sheet('P&ID-101')
        patterns.gas_branch(s, 200, 'N2', '0101', hv='HV-101', x={'hv': 80}, x_end=300)
        hv = next(i for i in s.items if i.get('id') == 'HV-101')
        self.assertEqual(hv['at'], [80, 200])


class Loop(unittest.TestCase):
    def test_route_is_orthogonal(self):
        for a, b in (((0, 0), (10, 5)), ((0, 0), (0, 5)), ((3, 3), (3, 3.0))):
            pts = patterns.route(a, b)
            for p, q in zip(pts, pts[1:]):
                self.assertTrue(abs(p[0] - q[0]) < 1e-9 or abs(p[1] - q[1]) < 1e-9)

    def test_loop_signal_kinds_and_connections(self):
        s, _ = build()
        ids = patterns.control_loop(s, '101', 'PI-101', 'FIC-101', 'XV-101', kind_in='electric', kind_out='pneumatic')
        lines = {i['id']: i for i in s.items if i['k'] == 'line' and i['id'] in ids}
        self.assertEqual(lines['S101a']['style'], 'Electrical Style')
        self.assertEqual(lines['S101b']['style'], 'Pneumatic Style')
        links = {(i['line'], i['asset'], i['ctx']) for i in s.items if i['k'] == 'connect'}
        self.assertIn(('S101a', 'PI-101', 'start'), links)
        self.assertIn(('S101b', 'XV-101', 'end'), links)

    def test_loop_requires_objects_drawn_first(self):
        s, _ = build()
        with self.assertRaises(KeyError):
            patterns.control_loop(s, '9', 'PI-101', 'NOPE-1', 'XV-101')


if __name__ == '__main__':
    unittest.main()
