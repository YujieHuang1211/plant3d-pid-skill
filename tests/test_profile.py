"""制图配置（建议书 3.1/4.2/4.4）：legacy 不变；pip-ref-a3 的交叉、间隙、箭头、接管、分层线宽、信号分类。"""
import json
import unittest

import _util
from _util import ROOT

import plain_convert as pc

CAT = json.loads((ROOT / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))


def convert(items, profile):
    pc.set_profile(profile)
    try:
        return pc.Conv(CAT).convert(items)
    finally:
        pc.set_profile('legacy-2026-10')


def line(lid, pts, style='Primary Style', **kw):
    return {'k': 'line', 'id': lid, 'style': style, 'pts': pts, **kw}


def polys_on(out, layer):
    return [i for i in out if i['k'] == 'poly' and i['layer'] == layer]


def cross_items():
    # H 横线（x 40→160, y=100）与 V 竖线（x=100, y 60→140）同为主线，十字交叉，互不连接
    return [line('H', [[40, 100], [160, 100]]), line('V', [[100, 60], [100, 140]])]


class Crossing(unittest.TestCase):
    def gap_of(self, out, ids_axis):
        # 找主线层里沿 axis 方向被断开的缺口宽度
        ps = polys_on(out, '管线-主')
        if ids_axis == 'y':          # 竖线：在 x=100 的折线按 y 排序，量中间缺口
            v = sorted([p['pts'] for p in ps if abs(p['pts'][0][0] - 100) < 1e-6 and abs(p['pts'][-1][0] - 100) < 1e-6], key=lambda q: q[0][1])
            return v[1][0][1] - v[0][-1][1] if len(v) == 2 else None
        h = sorted([p['pts'] for p in ps if abs(p['pts'][0][1] - 100) < 1e-6 and abs(p['pts'][-1][1] - 100) < 1e-6], key=lambda q: q[0][0])
        return h[1][0][0] - h[0][-1][0] if len(h) == 2 else None

    def test_legacy_breaks_horizontal_with_2_8_gap(self):
        out = convert(cross_items(), 'legacy-2026-10')
        self.assertAlmostEqual(self.gap_of(out, 'x'), 2.8, places=2)
        self.assertIsNone(self.gap_of(out, 'y'))

    def test_pip_breaks_vertical_with_0_13_inch_gap(self):
        out = convert(cross_items(), 'pip-ref-a3')
        self.assertAlmostEqual(self.gap_of(out, 'y'), 3.302, places=2)
        self.assertIsNone(self.gap_of(out, 'x'))

    def test_registered_tee_is_never_broken(self):
        items = cross_items() + [{'k': 'tee', 'line': 'V', 'to': 'H', 'start': True}]
        out = convert(items, 'pip-ref-a3')
        self.assertIsNone(self.gap_of(out, 'y'))
        self.assertIsNone(self.gap_of(out, 'x'))

    def test_signal_breaks_for_pipe_in_both_profiles(self):
        items = [line('H', [[40, 100], [160, 100]]), line('S', [[100, 60], [100, 140]], 'Electrical Style')]
        for prof in ('legacy-2026-10', 'pip-ref-a3'):
            out = convert(items, prof)
            self.assertEqual(len(polys_on(out, '管线-主')), 1, prof)       # 管线不断
            sig = [i for i in out if i['k'] == 'poly' and i['layer'].startswith('信号')]
            self.assertEqual(len(sig), 2, prof)                          # 信号线被断成两段


class Layers(unittest.TestCase):
    def test_pip_signal_kinds_have_own_layers_and_widths(self):
        items = [line('E', [[40, 50], [100, 50]], 'Electrical Style'), line('P', [[40, 60], [100, 60]], 'Pneumatic Style'),
                 line('D', [[40, 70], [100, 70]], 'Software Style')]
        out = convert(items, 'pip-ref-a3')
        pc.set_profile('pip-ref-a3')
        lay = {l['name']: l for l in pc.LAYERS}
        pc.set_profile('legacy-2026-10')
        self.assertEqual(lay['信号-电']['lw'], 25)
        self.assertEqual(lay['信号-气动']['lw'], 25)
        self.assertIn('ltype', lay['信号-数据'])
        self.assertNotEqual(lay['信号-电'].get('ltype'), lay['信号-数据'].get('ltype'))
        self.assertTrue(polys_on(out, '信号-气动') and polys_on(out, '信号-电') and polys_on(out, '信号-数据'))

    def test_pneumatic_has_slash_ticks_electric_has_none(self):
        out = convert([line('P', [[40, 60], [160, 60]], 'Pneumatic Style'), line('E', [[40, 80], [160, 80]], 'Electrical Style')], 'pip-ref-a3')
        self.assertGreater(len(polys_on(out, '信号-气动')), 1 + 6)       # 主线 + 每 15 mm 一对斜线
        self.assertEqual(len(polys_on(out, '信号-电')), 1)

    def test_legacy_pneumatic_still_shares_electric_layer(self):
        out = convert([line('P', [[40, 60], [160, 60]], 'Pneumatic Style')], 'legacy-2026-10')
        self.assertEqual(len(polys_on(out, '信号-电')), 1)

    def test_equipment_and_fitting_symbols_on_separate_layers_in_pip(self):
        items = [{'k': 'asset', 'id': 'V-101', 'style': 'Vessel Style', 'at': [100, 100]},
                 {'k': 'asset', 'id': 'HV-101', 'style': 'Ball Valve Style', 'at': [200, 100]}]
        out = convert(items, 'pip-ref-a3')
        lay = {i['style']: i['layer'] for i in out if i['k'] == 'sym'}
        self.assertEqual(lay['Vessel Style'], '设备')
        self.assertEqual(lay['Ball Valve Style'], '管件')
        out = convert(items, 'legacy-2026-10')
        self.assertEqual({i['layer'] for i in out if i['k'] == 'sym'}, {'符号'})


class Nozzle(unittest.TestCase):
    noz = [{'k': 'nozzle', 'id': 'N1', 'owner': 'V-101', 'at': [100, 100], 'rot': 0}]

    def test_legacy_default_is_flange(self):
        out = convert(self.noz, 'legacy-2026-10')
        self.assertEqual(len(polys_on(out, '符号')), 3)             # 接管 + 一对法兰线

    def test_pip_default_has_no_flange(self):
        out = convert(self.noz, 'pip-ref-a3')
        self.assertEqual(len(polys_on(out, '符号')), 1)

    def test_explicit_flange_in_pip(self):
        out = convert([dict(self.noz[0], conn='flange')], 'pip-ref-a3')
        self.assertEqual(len(polys_on(out, '符号')), 3)


class Arrows(unittest.TestCase):
    def arrows(self, out):
        return [i for i in out if i['k'] == 'sym' and i['style'] == 'Flow Arrow Style']

    def test_legacy_one_arrow_at_end_only(self):
        out = convert([line('L', [[40, 100], [120, 100], [120, 160], [200, 160]])], 'legacy-2026-10')
        self.assertEqual(len(self.arrows(out)), 1)

    def test_pip_arrows_after_each_corner_and_at_end(self):
        out = convert([line('L', [[40, 100], [120, 100], [120, 160], [200, 160]])], 'pip-ref-a3')
        self.assertEqual(len(self.arrows(out)), 3)

    def test_pip_short_segment_gets_no_corner_arrow(self):
        out = convert([line('L', [[40, 100], [120, 100], [120, 105], [200, 105]])], 'pip-ref-a3')
        ar = self.arrows(out)
        self.assertEqual(len(ar), 2)                                    # 第二个转角后一个 + 末段一个
        self.assertFalse([a for a in ar if abs(a['at'][0] - 120) < 1e-6])   # 5 mm 短竖段上不放


if __name__ == '__main__':
    unittest.main()
