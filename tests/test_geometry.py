"""统一几何（建议书 3.3）：预览、检查、转换、attach 用同一套换算；scale 含义不变。"""
import json
import unittest

import _util
from _util import ROOT

import geometry
import lint_specs
import pidlib

CAT = json.loads((ROOT / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))
NATIVE = next(k for k, v in CAT.items() if v.get('native'))
BALL = 'Ball Valve Style'          # Plant 库，默认比例 10（plant_style_scales.json）


class Factor(unittest.TestCase):
    def test_plant_style_scale_is_absolute(self):
        f, known = geometry.factor(BALL, 5)
        self.assertTrue(known)
        self.assertAlmostEqual(f, 0.5)

    def test_native_symbol_scale_is_multiplier(self):
        self.assertEqual(geometry.factor(NATIVE, 2), (2.0, True))

    def test_no_scale_is_one(self):
        self.assertEqual(geometry.factor(BALL, None), (1.0, True))

    def test_unknown_plant_default_is_flagged(self):
        self.assertEqual(geometry.factor('No Such Style', 3), (1.0, False))


class Ports(unittest.TestCase):
    def test_scaled_and_rotated_valve_ports(self):
        att = CAT[BALL]['att']
        pts = geometry.ports(CAT, BALL, (100, 100), 90, 5)       # 比例 5 = 默认 10 的一半，旋转 90°
        want = sorted((100 - dy * 0.5, 100 + dx * 0.5) for dx, dy in att)
        for p, w in zip(sorted(pts), want):
            self.assertAlmostEqual(p[0], w[0], places=6)
            self.assertAlmostEqual(p[1], w[1], places=6)

    def test_attach_uses_same_geometry(self):
        pidlib.use_model({})
        a = pidlib.attach(BALL, (100, 100), 'R', 0, 5)
        self.assertAlmostEqual(a[0], 100 + 4.0 * 0.5, places=2)
        self.assertAlmostEqual(a[1], 100, places=2)

    def test_lint_accepts_endpoint_on_scaled_port(self):
        items = [{'k': 'asset', 'id': 'V1', 'style': BALL, 'at': [100, 100], 'scale': 5},
                 {'k': 'line', 'id': 'L1', 'pts': [[80, 100], [102, 100]]},
                 {'k': 'connect', 'line': 'L1', 'asset': 'V1', 'ctx': 'end'}]
        errs, warns = [], []
        lint_specs.lint_sheet('P&ID-101', items, CAT, {'V1', 'L1'}, errs, warns)
        self.assertEqual(errs, [])
        self.assertEqual([w for w in warns if '连接点' in w], [])

    def test_lint_flags_plant_style_without_default_scale(self):
        cat = {'Fake Plant Style': {'bbox': [-4, -2, 4, 2], 'att': [[-4, 0], [4, 0]], 'plant_lib': True}}
        items = [{'k': 'asset', 'id': 'V1', 'style': 'Fake Plant Style', 'at': [100, 100], 'scale': 2}]
        errs, warns = [], []
        lint_specs.lint_sheet('P&ID-101', items, cat, {'V1'}, errs, warns)
        self.assertTrue(any('默认比例' in e for e in errs), errs)




class Legend(unittest.TestCase):
    def test_legend_rows_follow_profile(self):
        leg = pidlib.legend_rows('legacy-2026-10')
        pip = pidlib.legend_rows('pip-ref-a3')
        d = {r[0]: r for r in leg}
        p = {r[0]: r for r in pip}
        self.assertEqual(d['主工艺管线'][1], 0.7)
        self.assertEqual(d['电信号'][1], 0.18)
        self.assertEqual(p['电信号'][1], 0.25)
        self.assertEqual(p['气动信号'][2], '实线加双斜线')
        self.assertEqual(p['通信/数据链路'][2], '虚线')
        self.assertEqual({r[0] for r in pidlib.legend_rows('pip-ref-a3', {'Primary Style'})}, {'主工艺管线'})


if __name__ == '__main__':
    unittest.main()
