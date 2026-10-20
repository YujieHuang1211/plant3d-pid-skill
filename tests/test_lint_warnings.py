"""警告分级：编号、必须处置、已接受清单（按图 spec 哈希失效）。"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import _util
from _util import dump

import lint_specs


def run_lint(items, extra=(), accept=None):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        dump(t / 'P&ID-101.json', {'items': items})
        args = [str(t), 'P&ID-101', *extra]
        if accept is not None:
            dump(t / 'acc.json', accept)
            args += ['--accept', str(t / 'acc.json')]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = lint_specs.main(args)
        return ok, buf.getvalue()


OVERLAP = [{'k': 'text', 'at': [100, 100], 'text': 'ABC', 'h': 3.5}, {'k': 'text', 'at': [101, 100], 'text': 'XYZ', 'h': 3.5}]


class Warnings(unittest.TestCase):
    def test_overlap_is_plain_warning_by_default(self):
        ok, out = run_lint(OVERLAP)
        self.assertTrue(ok)
        self.assertIn('[W-TEXT-TEXT]', out)

    def test_blocked_code_becomes_error(self):
        ok, out = run_lint(OVERLAP, ['--block', 'W-TEXT-TEXT'])
        self.assertFalse(ok)
        self.assertIn('必须处置', out)

    def test_accepted_with_reason_passes(self):
        ok, out = run_lint(OVERLAP, ['--block', 'W-TEXT-TEXT'], accept=[{'code': 'W-TEXT-TEXT', 'match': '第 0 项', 'reason': '仪表圈内两行文字'}])
        self.assertTrue(ok, out)
        self.assertIn('已接受', out)

    def test_accept_without_reason_is_ignored(self):
        ok, _ = run_lint(OVERLAP, ['--block', 'W-TEXT-TEXT'], accept=[{'code': 'W-TEXT-TEXT', 'match': '第 0 项'}])
        self.assertFalse(ok)

    def test_accept_expires_when_sheet_changes(self):
        ok, _ = run_lint(OVERLAP, ['--block', 'W-TEXT-TEXT'],
                         accept=[{'code': 'W-TEXT-TEXT', 'match': '第 0 项', 'reason': 'r', 'sheet_sha': '000000000000'}])
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
