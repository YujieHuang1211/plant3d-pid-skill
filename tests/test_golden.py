"""示例项目（青木子）经 plain_convert 的输出必须与改动前的金样一致：图元种类、图层相同，数值差 ≤ 0.002 mm。
legacy-2026-10 配置下任何重构都不得改变老项目的图面。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _util
from _util import GOLDEN, ROOT

TOL = 0.002


def same(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f'{path}: 键不同 {sorted(set(a) ^ set(b))}']
        return [d for k in a for d in same(a[k], b[k], f'{path}.{k}')]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f'{path}: 长度 {len(a)} ≠ {len(b)}']
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in same(x, y, f'{path}[{i}]')]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return [] if abs(a - b) <= TOL else [f'{path}: {a} ≠ {b}']
    return [] if a == b else [f'{path}: {a!r} ≠ {b!r}']


class Golden(unittest.TestCase):
    def test_example_converts_like_baseline(self):
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory() as t:
            plant, plain = Path(t) / 'plant', Path(t) / 'plain'
            ex = ROOT / 'assets' / 'example'
            subprocess.run([sys.executable, 'gen_specs.py', str(plant)], cwd=ex, env=env, check=True, capture_output=True)
            subprocess.run([sys.executable, str(ROOT / 'scripts' / 'plain_convert.py'), str(plant), str(plain),
                            '--catalog', str(ROOT / 'assets' / 'symbol_catalog.json')], env=env, check=True, capture_output=True)
            gold = sorted((GOLDEN / 'plain_example').glob('*.json'))
            self.assertTrue(gold)
            for g in gold:
                new = plain / g.name
                self.assertTrue(new.exists(), g.name)
                diffs = same(json.loads(new.read_text(encoding='utf-8')), json.loads(g.read_text(encoding='utf-8')), g.stem)
                self.assertEqual(diffs[:5], [], f'{g.name} 共 {len(diffs)} 处不同')


if __name__ == '__main__':
    unittest.main()
