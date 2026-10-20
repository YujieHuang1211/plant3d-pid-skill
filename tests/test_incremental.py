"""增量重画：只画输入有变化的图（构建清单 + 输入哈希）。"""
import tempfile
import unittest
from pathlib import Path

import _util
from _util import dump, make_pdf

import plain_pipeline as pp


class Changed(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        w = Path(self.t.name)
        self.cfg = {'work': w, 'stage': w, 'project': 'fx', 'catalogs': [], 'plain': w / 'plain', 'pdf': w / 'pdf', 'prj': w / 'prj',
                    'model': {'meta': {}, 'sheets': [{'no': 'P&ID-101', 'title': 'a'}, {'no': 'P&ID-102', 'title': 'b'}]}}
        for n in ('P&ID-101', 'P&ID-102'):
            dump(w / 'plain' / f'{n}.json', {'items': [n]})
            dump(w / 'plain' / f'{n}.props.json', {'SheetTotal': '2'})
            make_pdf(w / 'pdf' / f'{n}.pdf')
            d = w / 'prj' / 'PID DWG' / pp.dwg_name(self.cfg, n)
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(b'dwg')
        self.nos = ['P&ID-101', 'P&ID-102']

    def tearDown(self):
        self.t.cleanup()

    def built(self):
        pp.update_manifest(self.cfg, {'run_id': 'r1', 'sheets': self.nos, 'inputs': pp.input_hashes(self.cfg, self.nos), 'global': pp.global_hash(self.cfg)})

    def test_no_manifest_means_everything(self):
        todo, why = pp.changed_sheets(self.cfg, self.nos)
        self.assertEqual(todo, self.nos)
        self.assertIn('没有构建清单', why)

    def test_nothing_changed_nothing_to_draw(self):
        self.built()
        self.assertEqual(pp.changed_sheets(self.cfg, self.nos)[0], [])

    def test_only_changed_sheet_redrawn(self):
        self.built()
        dump(self.cfg['plain'] / 'P&ID-102.json', {'items': ['changed']})
        self.assertEqual(pp.changed_sheets(self.cfg, self.nos)[0], ['P&ID-102'])

    def test_title_block_change_redraws_sheet(self):
        self.built()
        dump(self.cfg['plain'] / 'P&ID-101.props.json', {'SheetTotal': '3'})     # 增加一张图，总张数变了
        self.assertEqual(pp.changed_sheets(self.cfg, self.nos)[0], ['P&ID-101'])

    def test_missing_output_is_redrawn(self):
        self.built()
        (self.cfg['pdf'] / 'P&ID-101.pdf').unlink()
        self.assertEqual(pp.changed_sheets(self.cfg, self.nos)[0], ['P&ID-101'])

    def test_global_change_redraws_all(self):
        self.built()
        cat = Path(self.t.name) / 'cat.json'
        dump(cat, {'x': 1})
        self.cfg['catalogs'] = [str(cat)]
        todo, why = pp.changed_sheets(self.cfg, self.nos)
        self.assertEqual(todo, self.nos)
        self.assertIn('全部重画', why)



class Resume(Changed):
    """中断后续画：已完整出完且输入未变的图被认定；输入变了的图不沿用旧产物。"""
    def interrupted(self, done=('P&ID-101',)):
        import os
        import time
        started = time.time() - 100
        for n in self.nos:
            os.utime(self.cfg['pdf'] / f'{n}.pdf', (started - 50, started - 50))       # 先全部置为旧文件
            d = self.cfg['prj'] / 'PID DWG' / pp.dwg_name(self.cfg, n)
            os.utime(d, (started - 50, started - 50))
        for n in done:                                                                      # 本次出完的图
            os.utime(self.cfg['pdf'] / f'{n}.pdf', None)
            os.utime(self.cfg['prj'] / 'PID DWG' / pp.dwg_name(self.cfg, n), None)
        rec = {'run_id': 'r2', 'state': 'interrupted', 'started': started, 'sheets': self.nos,
               'inputs': pp.input_hashes(self.cfg, self.nos), 'global': pp.global_hash(self.cfg)}
        (self.cfg['work'] / '_出图日志').mkdir(exist_ok=True)
        pp.write_record(self.cfg, rec)
        return rec

    def test_salvages_only_completed_sheets(self):
        rec = self.interrupted()
        self.assertEqual(pp.salvage(self.cfg, rec), ['P&ID-101'])
        self.assertEqual(pp.changed_sheets(self.cfg, self.nos)[0], ['P&ID-102'])

    def test_changed_input_is_not_salvaged(self):
        rec = self.interrupted()
        dump(self.cfg['plain'] / 'P&ID-101.json', {'items': ['edited after the interrupted run']})
        self.assertEqual(pp.salvage(self.cfg, rec), [])
        self.assertEqual(pp.changed_sheets(self.cfg, self.nos)[0], self.nos)

    def test_ok_run_has_nothing_to_salvage(self):
        rec = self.interrupted()
        rec['state'] = 'ok'
        self.assertEqual(pp.salvage(self.cfg, rec), [])


if __name__ == '__main__':
    unittest.main()
