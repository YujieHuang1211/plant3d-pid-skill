"""ISO 10628-2 风格符号：依据字段齐全、闭合图形真闭合、替换后端口与原符号一致、legacy 配置不受影响、输出为带几何的块。"""
import json
import unittest

import _util
from _util import ROOT

import drawprofile
import iso_symbols as iso
import plain_convert as pc
import symbol_geom

CAT = json.loads((ROOT / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))


def convert(items, profile):
    pc.set_profile(profile)
    try:
        return pc.Conv(CAT).convert(items)
    finally:
        pc.set_profile('legacy-2026-10')


class Defs(unittest.TestCase):
    def test_every_symbol_has_basis(self):
        for k, d in iso.ISO_DEFS.items():
            b = d['basis']
            for f in ('std', 'item', 'reg', 'pdf_page', 'printed_page', 'verified'):
                self.assertIn(f, b, k)
            self.assertEqual(b['printed_page'], b['pdf_page'] - 4, k)
            self.assertTrue(d.get('block'), k)

    def test_closed_paths_return_to_start(self):
        for k, d in iso.ISO_DEFS.items():
            for p in d['paths']:
                if p['closed']:
                    self.assertEqual(p['pts'][0], p['pts'][-1], k)
                    self.assertGreater(len(p['pts']), 3, k)      # 转换器只把点数大于 3 的闭合折线画成闭合

    def test_assets_in_sync_with_definitions(self):
        """改了 iso_symbols.py 必须重新 build-native，否则 assets 里的几何过期"""
        native = json.loads((ROOT / 'assets' / 'native_symbols.json').read_text(encoding='utf-8'))
        for k, d in iso.ISO_DEFS.items():
            self.assertIn(k, native, k)
            self.assertEqual(native[k]['paths'], d['paths'], k + ' 过期，运行 symbol_geom.py build-native')
            self.assertTrue(native[k]['block'])


class Mapping(unittest.TestCase):
    def test_map_targets_exist_and_ports_match_source(self):
        """换符号不能让管线接口错位：有端口记录的源符号，ISO 符号的接口点必须相同"""
        P = drawprofile.load('pip-ref-a3')
        self.assertTrue(P['symbol_map'])
        for src, dst in P['symbol_map'].items():
            self.assertIn(dst, iso.ISO_DEFS, dst)
            att = CAT[src].get('att')
            if att:
                ports = sorted(tuple(v) for v in iso.ISO_DEFS[dst]['ports'].values())
                self.assertEqual(ports, sorted(tuple(a) for a in att), f'{src}→{dst}')

    def test_legacy_profile_keeps_plant_styles(self):
        out = convert([{'k': 'asset', 'id': 'HV-1', 'style': 'Ball Valve Style', 'at': [100, 100]}], 'legacy-2026-10')
        syms = [i for i in out if i['k'] == 'sym']
        self.assertEqual([s['style'] for s in syms], ['Ball Valve Style'])
        self.assertNotIn('geom', syms[0])

    def test_pip_profile_emits_one_block_with_geometry(self):
        out = convert([{'k': 'asset', 'id': 'HV-1', 'style': 'Ball Valve Style', 'at': [100, 100], 'rot': 90}], 'pip-ref-a3')
        syms = [i for i in out if i['k'] == 'sym']
        self.assertEqual(len(syms), 1)
        s = syms[0]
        self.assertEqual(s['style'], 'ISO Ball Valve Style')
        self.assertTrue(s['geom'])
        self.assertEqual(s['rot'], 90)
        self.assertEqual(s['layer'], '管件')
        self.assertFalse([i for i in out if i['k'] == 'poly' and i['layer'] == '管件' and i['pts'][0][0] in range(96, 105)])   # 不再散成折线

    def test_plant_absolute_scale_becomes_multiplier(self):
        default = json.loads((ROOT / 'assets' / 'plant_style_scales.json').read_text(encoding='utf-8'))['Ball Valve Style']['scale']
        out = convert([{'k': 'asset', 'id': 'HV-1', 'style': 'Ball Valve Style', 'at': [0, 0], 'scale': default * 0.5}], 'pip-ref-a3')
        self.assertAlmostEqual([i for i in out if i['k'] == 'sym'][0]['scale'], 0.5)

    def test_unmapped_style_unchanged_in_pip(self):
        out = convert([{'k': 'asset', 'id': 'CK-1', 'style': 'Check Valve Style', 'at': [0, 0]}], 'pip-ref-a3')
        self.assertEqual([i['style'] for i in out if i['k'] == 'sym'], ['Check Valve Style'])

    def test_project_override_can_switch_mapping_off(self):
        item = [{'k': 'asset', 'id': 'HV-1', 'style': 'Ball Valve Style', 'at': [0, 0]}]
        P = drawprofile.merge(drawprofile.load('pip-ref-a3'), {'symbol_map': {'*': None}})
        self.assertEqual([i['style'] for i in convert(item, P) if i['k'] == 'sym'], ['Ball Valve Style'])
        P = drawprofile.merge(drawprofile.load('pip-ref-a3'), {'symbol_map': {'Ball Valve Style': None}})
        self.assertEqual([i['style'] for i in convert(item, P) if i['k'] == 'sym'], ['Ball Valve Style'])

    def test_mirror_passes_through(self):
        out = convert([{'k': 'asset', 'id': 'PSV-1', 'style': 'QMZ Safety Valve Style', 'at': [0, 0], 'mirror': True}], 'pip-ref-a3')
        self.assertTrue([i for i in out if i['k'] == 'sym'][0]['mirror'])


if __name__ == '__main__':
    unittest.main()
