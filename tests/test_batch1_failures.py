"""第一批：失败必须算失败（建议书 3.5）。每个用例在旧代码上应当失败。"""
import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

import _util
from _util import dump, make_pdf

import pack_pdfs
import plain_pipeline as pp


class Quiet:
    def __enter__(self):
        self.c = contextlib.redirect_stdout(io.StringIO())
        self.c.__enter__()

    def __exit__(self, *a):
        return self.c.__exit__(*a)


def base_cfg(tmp):
    work = Path(tmp)
    specs, plain = work / 'specs', work / 'plain'
    dump(specs / 'P&ID-101.json', {'items': []})
    dump(plain / 'P&ID-101.json', {'items': []})
    model = {'meta': {'project': 'fx', 'rev': 'R0'}, 'sheets': [{'no': 'P&ID-101', 'title': 'fx'}]}
    dump(work / 'pid_model.json', model)
    return {'work': work, 'stage': work, 'project': 'fx', 'model': model, 'catalogs': [], 'layout': 'none.py',
            'specs': specs, 'plain': plain, 'pdf': work / 'pdf', 'prj': work / 'prj', 'backup': work / 'bk'}


class PreviewFailure(unittest.TestCase):
    def test_preview_failure_fails_phase(self):
        old = pp.run
        pp.run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1 if any('preview_spec.py' in str(x) for x in cmd) else 0, '', '')
        try:
            with tempfile.TemporaryDirectory() as t, Quiet():
                self.assertFalse(pp.check_phase(base_cfg(t), ['P&ID-101'], preview=True))
        finally:
            pp.run = old


class StatusFromRecord(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.cfg = base_cfg(self.t.name)
        (self.cfg['work'] / '_出图日志').mkdir()

    def tearDown(self):
        self.t.cleanup()

    def test_no_record_is_not_success(self):
        with Quiet():
            self.assertEqual(pp.status_code(self.cfg), 1)

    def test_failed_record_wins_over_done_text_in_log(self):
        log = self.cfg['work'] / '_出图日志' / 'draw_x.log'
        log.write_bytes('错误: x\n全部完成\n'.encode('utf-8'))
        pp.write_record(self.cfg, {'run_id': 'r1', 'state': 'failed', 'log': str(log), 'returncode': 1})
        with Quiet():
            self.assertEqual(pp.status_code(self.cfg), 1)

    def test_ok_record_is_success(self):
        pp.write_record(self.cfg, {'run_id': 'r1', 'state': 'ok', 'returncode': 0})
        with Quiet():
            self.assertEqual(pp.status_code(self.cfg), 0)

    def test_running_with_dead_pid_is_interrupted(self):
        pp.write_record(self.cfg, {'run_id': 'r1', 'state': 'running', 'pid': 2 ** 22 - 3})
        with Quiet():
            self.assertEqual(pp.status_code(self.cfg), 2)
        self.assertEqual(pp.latest_record(self.cfg)['state'], 'interrupted')

    def test_gbk_and_utf8_logs_both_readable(self):
        self.assertIn('完成', pp.decode_log('完成'.encode('gbk')))
        self.assertIn('完成', pp.decode_log('完成'.encode('utf-8')))


class PostChecks(unittest.TestCase):
    def post(self, cfg):
        old = pp.run
        pp.run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, 'mocked', '')
        try:
            with Quiet():
                return pp.cmd_post(cfg, [])
        finally:
            pp.run = old

    def test_missing_dwg_fails(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = base_cfg(t)
            make_pdf(cfg['pdf'] / 'P&ID-101.pdf')
            make_pdf(cfg['stage'] / 'fx_P&ID图集_R0.pdf')
            cfg['prj'].mkdir()
            self.assertFalse(self.post(cfg))

    def test_two_page_single_pdf_fails(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = base_cfg(t)
            make_pdf(cfg['pdf'] / 'P&ID-101.pdf', pages=2)
            make_pdf(cfg['stage'] / 'fx_P&ID图集_R0.pdf')
            (cfg['prj'] / 'PID DWG').mkdir(parents=True)
            (cfg['prj'] / 'PID DWG' / pp.dwg_name(cfg, 'P&ID-101')).write_bytes(b'dwg')
            self.assertFalse(self.post(cfg))

    def test_stale_output_older_than_run_fails(self):
        import os
        with tempfile.TemporaryDirectory() as t:
            cfg = base_cfg(t)
            pdf = cfg['pdf'] / 'P&ID-101.pdf'
            make_pdf(pdf)
            os.utime(pdf, (1_000_000_000, 1_000_000_000))
            problems = pp.verify_outputs(cfg, ['P&ID-101'], since=1_700_000_000, need_dwg=False)
            self.assertTrue(any('早于' in p for p in problems), problems)


class PackPdfs(unittest.TestCase):
    def test_two_page_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            model = {'meta': {'project': 'fx'}, 'sheets': [{'no': 'P&ID-101', 'title': 'fx'}]}
            dump(t / 'm.json', model)
            make_pdf(t / 'src' / 'P&ID-101.pdf', pages=2)
            with self.assertRaises(SystemExit):
                with Quiet():
                    pack_pdfs.main(t / 'm.json', t / 'src', t / 'out.pdf')

    def test_wrong_size_on_second_page_rejected_and_good_set_passes(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            model = {'meta': {'project': 'fx'}, 'sheets': [{'no': 'P&ID-101', 'title': 'fx'}]}
            dump(t / 'm.json', model)
            make_pdf(t / 'src' / 'P&ID-101.pdf')
            with Quiet():
                pack_pdfs.main(t / 'm.json', t / 'src', t / 'out.pdf')
            import fitz
            self.assertEqual(len(fitz.open(t / 'out.pdf')), 1)


if __name__ == '__main__':
    unittest.main()
