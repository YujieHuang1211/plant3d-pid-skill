"""第一批：模型覆盖、位号绑定、转换后几何（建议书 3.2、3.3）。旧代码上应失败。"""
import contextlib
import io
import unittest

import _util  # noqa: F401

import lint_specs
import validate_views as vv


def lint(items, cat=None):
    errs, warns = [], []
    lint_specs.lint_sheet('P&ID-101', items, cat or {}, set(), errs, warns)
    return errs, warns


class PlainGeometry(unittest.TestCase):
    def test_polyline_outside_frame_is_error(self):
        errs, _ = lint([{'k': 'poly', 'pts': [[0, 0], [500, 400]], 'layer': '管线-主'}])
        self.assertTrue(any('超出图框' in e for e in errs), errs)

    def test_polyline_inside_frame_ok(self):
        errs, _ = lint([{'k': 'poly', 'pts': [[40, 100], [200, 100]], 'layer': '管线-主'}])
        self.assertEqual(errs, [])

    def test_polyline_in_title_block_is_error(self):
        errs, _ = lint([{'k': 'poly', 'pts': [[240, 50], [300, 50]], 'layer': '管线-主'}])
        self.assertTrue(any('标题栏' in e for e in errs), errs)

    def test_sym_in_title_block_is_error(self):
        errs, _ = lint([{'k': 'sym', 'style': 'x', 'at': [300, 50], 'layer': '符号'}])
        self.assertTrue(any('标题栏' in e for e in errs), errs)


def model():
    return {'boundary': [{'id': 'BL-A'}], 'equipment': [{'tag': 'V-101'}],
            'inline': [{'tag': 'HV-101'}], 'instruments': [{'tag': 'PT-102'}],
            'lines': [{'no': 'N2-0101-6-S1', 'seq': ['BL-A', 'HV-101', 'V-101']}],
            'sheets': [{'no': 'P&ID-101'}]}


def plant(extra=()):
    return {'P&ID-101': [
        {'k': 'line', 'id': 'L1', 'style': 'Primary Style', 'pts': [[50, 100], [150, 100]],
         'group': {'Service': 'N2', 'LineNumber': '0101', 'NominalSize': '6', 'NominalSpec': 'S1'}},
        {'k': 'asset', 'id': 'BL-A', 'style': 'QMZ Battery Limit Style', 'at': [40, 100]},
        {'k': 'asset', 'id': 'HV-101', 'style': 'Ball Valve Style', 'at': [80, 100], 'anno': {'style': 'Oval Tag Style', 'at': [80, 90]}},
        {'k': 'asset', 'id': 'V-101', 'style': 'Vessel Style', 'at': [170, 100], 'anno': {'style': 'Equipment Tag', 'at': [170, 90]}},
        {'k': 'asset', 'id': 'PT-102', 'style': 'Field Mounted Discrete Instrument Style', 'at': [100, 130], 'anno': {'style': 'Instrument Bubble Style', 'at': [100, 130]}},
        {'k': 'connect', 'line': 'L1', 'asset': 'BL-A', 'ctx': 'start'},
        {'k': 'connect', 'line': 'L1', 'asset': 'HV-101', 'ctx': 'inline'},
        {'k': 'connect', 'line': 'L1', 'asset': 'V-101', 'ctx': 'end'},
        *extra]}


def plain(split_apart=False):
    t = lambda at, s: {'k': 'text', 'at': at, 'text': s, 'h': 2.4, 'just': 'MC'}
    items = [t([80, 90], 'HV-101'), t([170, 90], 'V-101'), t([40, 110], 'BL-A'), t([100, 100], 'N2-0101-6-S1')]
    items += [t([100, 131.5], 'PT'), t([300 if split_apart else 100, 128.5], '102')]
    return {'P&ID-101': items}


class Coverage(unittest.TestCase):
    def run_vv(self, m, pl, pn):
        errs, warns = vv.validate(m, pl, pn)
        return errs, warns

    def test_complete_set_passes(self):
        errs, _ = self.run_vv(model(), plant(), plain())
        self.assertEqual(errs, [])

    def test_empty_specs_fail_when_model_has_objects(self):
        errs, _ = self.run_vv(model(), {'P&ID-101': []}, {'P&ID-101': []})
        for tag in ('BL-A', 'V-101', 'HV-101', 'PT-102'):
            self.assertTrue(any(tag in e and '没有主表示' in e for e in errs), (tag, errs))

    def test_omitted_with_reason_is_accepted(self):
        m = model()
        m['instruments'][0]['omitted'] = '本阶段不画，见待确认 Q-03'
        pl = plant()
        pl['P&ID-101'] = [i for i in pl['P&ID-101'] if i.get('id') != 'PT-102']
        errs, _ = self.run_vv(m, pl, plain())
        self.assertEqual([e for e in errs if 'PT-102' in e], [])

    def test_unapproved_extra_object(self):
        errs, _ = self.run_vv(model(), plant([{'k': 'asset', 'id': 'XV-999', 'style': 'Ball Valve Style', 'at': [120, 100]}]), plain())
        self.assertTrue(any('XV-999' in e and '模型里没有' in e for e in errs), errs)

    def test_split_tag_far_apart_is_not_a_tag(self):
        errs, _ = self.run_vv(model(), plant(), plain(split_apart=True))
        self.assertTrue(any('PT-102' in e for e in errs), errs)

    def test_object_on_wrong_declared_sheet(self):
        m = model()
        m['equipment'][0]['sheet'] = 'P&ID-102'
        errs, _ = self.run_vv(m, plant(), plain())
        self.assertTrue(any('V-101' in e and 'P&ID-102' in e for e in errs), errs)

    def test_line_sequence_object_not_connected_to_line(self):
        pl = plant()
        pl['P&ID-101'] = [i for i in pl['P&ID-101'] if not (i['k'] == 'connect' and i['asset'] == 'HV-101')]
        errs, _ = self.run_vv(model(), pl, plain())
        self.assertTrue(any('HV-101' in e and 'N2-0101-6-S1' in e for e in errs), errs)


if __name__ == '__main__':
    unittest.main()
