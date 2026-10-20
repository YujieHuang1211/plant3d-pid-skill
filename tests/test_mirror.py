"""mirror：安全阀保持直立（rot=0）而进出口左右互换，用来替代“旋转符号凑空间”。"""
import json
import unittest

import _util
from _util import ROOT

import geometry
import lint_specs
import plain_convert as pc

CAT = json.loads((ROOT / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))
NATIVE = next(k for k, v in CAT.items() if v.get('native') and v.get('att'))


class Mirror(unittest.TestCase):
    def test_ports_swap_sides(self):
        a = geometry.ports(CAT, NATIVE, (100, 100), 0, None, False)
        b = geometry.ports(CAT, NATIVE, (100, 100), 0, None, True)
        for (x1, y1), (x2, y2) in zip(a, b):
            self.assertAlmostEqual(x1 - 100, -(x2 - 100), places=6)
            self.assertAlmostEqual(y1, y2, places=6)

    def test_box_mirrors_about_insertion_point(self):
        b0 = geometry.box(CAT, 'QMZ Safety Valve Style', (100, 100), 0, None, False)
        b1 = geometry.box(CAT, 'QMZ Safety Valve Style', (100, 100), 0, None, True)
        self.assertAlmostEqual(b0[0] - 100, -(b1[2] - 100), places=6)
        self.assertAlmostEqual(b0[1], b1[1], places=6)

    def test_mirrored_psv_at_rot0_passes_upright_rule(self):
        lint_specs.set_profile('pip-ref-a3')
        try:
            errs, warns = [], []
            lint_specs.lint_sheet('P&ID-107', [{'k': 'asset', 'id': 'PSV-1', 'style': 'QMZ Safety Valve Style', 'at': [100, 100], 'mirror': True}],
                                  CAT, {'PSV-1'}, errs, warns)
            self.assertEqual([e for e in errs if '安全阀' in e], [])
        finally:
            lint_specs.set_profile('legacy-2026-10')

    def test_converter_passes_mirror_to_engine_sym_and_native_polys(self):
        pc.set_profile('legacy-2026-10')
        out = pc.Conv(CAT).convert([{'k': 'asset', 'id': 'PSV-1', 'style': 'QMZ Safety Valve Style', 'at': [100, 100], 'mirror': True}])
        self.assertTrue(any(i['k'] == 'sym' and i.get('mirror') for i in out))
        n = pc.Conv(CAT).convert([{'k': 'asset', 'id': 'X-1', 'style': NATIVE, 'at': [100, 100]}])
        m = pc.Conv(CAT).convert([{'k': 'asset', 'id': 'X-1', 'style': NATIVE, 'at': [100, 100], 'mirror': True}])
        xs = lambda out: sorted(round(p[0] - 100, 3) for i in out if i['k'] == 'poly' for p in i['pts'])
        self.assertEqual(xs(m), sorted(-v for v in xs(n)))


if __name__ == '__main__':
    unittest.main()
