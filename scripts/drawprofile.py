"""制图配置加载：assets/profiles/<名字>.json。缺省 legacy-2026-10（老项目复跑图面不变）。
用法（其他脚本里）: import drawprofile as prof; P = prof.load('pip-ref-a3')；P['sheet']、P['layers'] …
pipeline.json 的 "profile" 键给名字；新项目由 new_project.py 写入 pip-ref-a3。
"""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / 'assets' / 'profiles'
DEFAULT = 'legacy-2026-10'
NEW_PROJECT_DEFAULT = 'pip-ref-a3'


def load(name=None):
    name = name or DEFAULT
    f = Path(name) if str(name).endswith('.json') else DIR / f'{name}.json'
    if not f.exists():
        raise SystemExit(f'没有制图配置 {name}（可用：{", ".join(p.stem for p in DIR.glob("*.json"))}）')
    return json.loads(f.read_text(encoding='utf-8'))


def sheet(P):
    s = P['sheet']
    return dict(s, frame=tuple(s['frame']), title_block=tuple(s['title_block']))
