"""编号语义（建议书 3.4）：位号唯一 ≠ 编号连续；引用不是重复；历史编号可保留。"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import _util
from _util import dump

import check_numbering as cn
import check_plain as cp
import validate_views as vv


def run(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = fn(*a, **kw)
    return ok, buf.getvalue()


def model(**extra):
    m = {'lines': [{'no': 'N2-0101-6-S1'}, {'no': 'N2-0103-6-S1'}],      # 0102 缺号
         'interlocks': [{'id': 'I-01'}, {'id': 'I-03'}],                   # I-02 缺号
         'equipment': [{'tag': 'V101'}], 'inline': [], 'instruments': [{'tag': 'PT-102'}], 'boundary': []}
    m.update(extra)
    return m


def check(m, profile):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        dump(t / 'm.json', m)
        (t / 'specs').mkdir()
        return run(cn.main, t / 'm.json', t / 'specs', profile)


class Gaps(unittest.TestCase):
    def test_legacy_requires_continuous(self):
        ok, out = check(model(), 'legacy-2026-10')
        self.assertFalse(ok)
        self.assertIn('不连续', out)

    def test_stable_gap_is_warning_not_error(self):
        ok, out = check(model(), 'pip-ref-a3')
        self.assertTrue(ok, out)
        self.assertIn('WARN', out)

    def test_stable_retired_numbers_silence_warning(self):
        ok, out = check(model(retired={'line_seq': ['0102'], 'interlocks': ['I-02']}), 'pip-ref-a3')
        self.assertTrue(ok)
        self.assertNotIn('WARN', out)

    def test_stable_duplicate_line_seq_is_error(self):
        m = model()
        m['lines'].append({'no': 'H2-0101-6-S1'})
        ok, out = check(m, 'pip-ref-a3')
        self.assertFalse(ok)


class Loops(unittest.TestCase):
    def test_declared_loop_with_missing_final_element_is_error(self):
        m = model(loops=[{'id': 'FIC-101', 'measure': 'PT-102', 'control': 'PT-102', 'final': 'XV-999', 'signal': 'electric'}])
        ok, out = check(m, 'pip-ref-a3')
        self.assertFalse(ok)
        self.assertIn('XV-999', out)

    def test_no_hardcoded_fic_rule_in_stable_mode(self):
        m = model()
        m['instruments'].append({'tag': 'FIC-101'})
        ok, out = check(m, 'pip-ref-a3')
        self.assertNotIn('FIC-101 没有同号', out)

    def test_legacy_keeps_fic_rule(self):
        m = model(lines=[], interlocks=[])
        m['instruments'].append({'tag': 'FIC-101'})
        ok, out = check(m, 'legacy-2026-10')
        self.assertIn('FIC-101 没有同号', out)


class TagPattern(unittest.TestCase):
    def test_tag_without_hyphen_is_recognised_when_configured(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            m = model(conventions={'tag_pattern': r'[A-Z]{1,4}-?\d{3}[A-Z]?'}, lines=[], interlocks=[])
            dump(t / 'm.json', m)
            dump(t / 'specs' / 'P&ID-101.json', {'items': [{'k': 'text', 'at': [50, 50], 'text': 'V101 与 V999'}]})
            ok, out = run(cn.main, t / 'm.json', t / 'specs', 'pip-ref-a3')
            self.assertFalse(ok)
            self.assertIn('V999', out)
            self.assertNotIn('V101 不在', out)


class References(unittest.TestCase):
    def specs(self, t, second):
        a = {'items': [{'k': 'asset', 'id': 'PT-102', 'style': 'Field Mounted Discrete Instrument Style', 'at': [50, 50]}]}
        dump(t / 'src' / 'P&ID-101.json', a)
        dump(t / 'src' / 'P&ID-102.json', {'items': [second]})
        for n, items in (('P&ID-101', [{'k': 'text', 'at': [50, 51.5], 'text': 'PT', 'h': 2.4}, {'k': 'text', 'at': [50, 48.5], 'text': '102', 'h': 2.4}]),
                         ('P&ID-102', [{'k': 'text', 'at': [50, 51.5], 'text': 'PT', 'h': 2.4}, {'k': 'text', 'at': [50, 48.5], 'text': '102', 'h': 2.4}])):
            dump(t / 'dst' / f'{n}.json', {'items': items})

    def test_second_primary_on_other_sheet_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            self.specs(t, {'k': 'asset', 'id': 'PT-102', 'style': 'Field Mounted Discrete Instrument Style', 'at': [50, 50]})
            ok, out = run(cp.main, [str(t / 'src'), str(t / 'dst')])
            self.assertFalse(ok)
            self.assertIn('多张图', out)

    def test_reference_instance_is_allowed(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            self.specs(t, {'k': 'asset', 'id': 'PT-102@102', 'ref_of': 'PT-102', 'style': 'Field Mounted Discrete Instrument Style', 'at': [50, 50]})
            ok, out = run(cp.main, [str(t / 'src'), str(t / 'dst')])
            self.assertTrue(ok, out)

    def test_validate_views_accepts_reference_and_rejects_dangling_reference(self):
        m = {'instruments': [{'tag': 'PT-102'}], 'equipment': [], 'inline': [], 'boundary': [], 'lines': []}
        base = {'k': 'asset', 'id': 'PT-102', 'style': 'Field Mounted Discrete Instrument Style', 'at': [50, 50]}
        ref = dict(base, id='PT-102@102', ref_of='PT-102')
        pl = {'P&ID-101': [base], 'P&ID-102': [ref]}
        txt = [{'k': 'text', 'at': [50, 51.5], 'text': 'PT', 'h': 2.4}, {'k': 'text', 'at': [50, 48.5], 'text': '102', 'h': 2.4}]
        errs, _ = vv.validate(m, pl, {'P&ID-101': txt, 'P&ID-102': txt})
        self.assertEqual(errs, [])
        errs, _ = vv.validate(m, {'P&ID-102': [ref]}, {'P&ID-102': txt})
        self.assertTrue(any('PT-102' in e for e in errs), errs)


if __name__ == '__main__':
    unittest.main()
