"""重开核查：用合成的 info 清单检查数量、文字、图层、越框。"""
import unittest

import _util  # noqa: F401

import reopen_plain as rp

FRAME = (25, 5, 415, 292)
INFO = """=== t info x
图纸: x.dwg  EXTMIN=(25,5,0) EXTMAX=(415,292,0)
Polyline h=1 layer=未打印 [25.0,5.0]-[415.0,292.0]
Polyline h=2 layer=未打印 [235.0,5.0]-[415.0,89.0]
MText h=3 layer=位号 [50.0,50.0]-[60.0,52.0] mtext=HV-101
Polyline h=4 layer=管线-主 [40.0,100.0]-[90.0,100.0]
BlockReference h=5 layer=符号 [60.0,98.0]-[68.0,102.0] block=球阀
"""
ITEMS = [{'k': 'text', 'at': [50, 50], 'text': 'HV-101', 'h': 2.5, 'layer': '位号'},
         {'k': 'poly', 'pts': [[40, 100], [90, 100]], 'layer': '管线-主'},
         {'k': 'sym', 'style': 'Ball Valve Style', 'at': [64, 100], 'layer': '符号'}]
LAYERS = {'位号', '管线-主', '符号'}


class Reopen(unittest.TestCase):
    def test_matching_drawing_passes(self):
        self.assertTrue(rp.check(INFO, ITEMS, LAYERS, FRAME)['pass'])

    def test_missing_entity_fails(self):
        info = INFO.replace('BlockReference h=5 layer=符号 [60.0,98.0]-[68.0,102.0] block=球阀\n', '')
        r = rp.check(info, ITEMS, LAYERS, FRAME)
        self.assertFalse(r['pass'])
        self.assertTrue(any('BlockReference' in f for f in r['fails']))

    def test_missing_text_fails(self):
        r = rp.check(INFO.replace('mtext=HV-101', 'mtext=HV-999'), ITEMS, LAYERS, FRAME)
        self.assertTrue(any('找不到文字' in f for f in r['fails']))

    def test_unknown_layer_and_out_of_frame_fail(self):
        info = INFO.replace('layer=管线-主 [40.0,100.0]-[90.0,100.0]', 'layer=杂项 [40.0,100.0]-[500.0,100.0]')
        fails = rp.check(info, ITEMS, LAYERS, FRAME)['fails']
        self.assertTrue(any('图层' in f for f in fails))
        self.assertTrue(any('越出图框' in f for f in fails))

    def test_not_opened_fails(self):
        self.assertFalse(rp.check('', ITEMS, LAYERS, FRAME)['pass'])

    def test_table_makes_counts_lower_bounds(self):
        items = ITEMS + [{'k': 'table', 'at': [30, 200], 'cols': [10], 'rowh': 5, 'rows': [['a']]}]
        info = INFO + 'Polyline h=6 layer=符号 [30.0,190.0]-[40.0,200.0]\n'
        self.assertTrue(rp.check(info, items, LAYERS, FRAME)['pass'])


if __name__ == '__main__':
    unittest.main()
