"""检查点校验：完整性、输入哈希、旧备份无清单。"""
import tempfile
import unittest
import zipfile
from pathlib import Path

import _util
from _util import dump

import ckpt


class Ckpt(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        t = Path(self.t.name)
        self.specs = t / 'specs'
        dump(self.specs / 'P&ID-101.json', {'items': [1]})
        dump(self.specs / 'P&ID-101.props.json', {'SheetTotal': '2'})
        self.zip = t / 'prj_P&ID-101_通过后.zip'
        with zipfile.ZipFile(self.zip, 'w') as z:
            z.writestr('a.txt', 'x')

    def tearDown(self):
        self.t.cleanup()

    def test_ok_when_inputs_unchanged(self):
        ckpt.write(self.zip, self.specs, ['P&ID-101'], 'r1')
        self.assertEqual(ckpt.verify(self.zip, self.specs), [])

    def test_refused_when_done_sheet_spec_changed(self):
        ckpt.write(self.zip, self.specs, ['P&ID-101'], 'r1')
        dump(self.specs / 'P&ID-101.json', {'items': [2]})
        p = ckpt.verify(self.zip, self.specs)
        self.assertTrue(p and '变了' in p[0], p)

    def test_refused_without_manifest(self):
        p = ckpt.verify(self.zip, self.specs)
        self.assertTrue(p and '没有身份清单' in p[0], p)

    def test_refused_when_zip_tampered_or_corrupt(self):
        ckpt.write(self.zip, self.specs, ['P&ID-101'], 'r1')
        with zipfile.ZipFile(self.zip, 'a') as z:
            z.writestr('b.txt', 'y')
        self.assertTrue(any('哈希' in p for p in ckpt.verify(self.zip, self.specs)))
        self.zip.write_bytes(b'not a zip')
        self.assertTrue(any('完整' in p for p in ckpt.verify(self.zip, self.specs)))

    def test_cli_exit_codes(self):
        ckpt.write(self.zip, self.specs, ['P&ID-101'])
        self.assertEqual(ckpt.main(['verify', str(self.zip), str(self.specs)]), 0)
        dump(self.specs / 'P&ID-101.props.json', {'SheetTotal': '9'})
        self.assertEqual(ckpt.main(['verify', str(self.zip), str(self.specs)]), 1)


    def test_dbcopy_makes_consistent_copy_of_open_database(self):
        import sqlite3
        t = Path(self.t.name)
        prj = t / 'prj'
        prj.mkdir()
        db = sqlite3.connect(prj / 'x.dcf')
        db.execute('create table a(v)')
        db.execute('insert into a values (1)')
        db.commit()
        db.execute('begin')                           # 库被另一个连接打开且有未提交事务
        db.execute('insert into a values (2)')
        res = ckpt.dbcopy(prj, t / 'out')
        self.assertEqual([r[1] for r in res], [True])
        cp = sqlite3.connect(t / 'out' / 'x.dcf')
        self.assertEqual(cp.execute('select count(*) from a').fetchone()[0], 1)   # 只含已提交数据
        cp.close()
        db.rollback()
        db.close()


if __name__ == '__main__':
    unittest.main()
