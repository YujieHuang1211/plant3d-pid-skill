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


def merge(base, over):
    """把项目覆盖项深度合并进配置（dict 逐层合并，其余直接替换）"""
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def effective(name, overrides, out_file, note=''):
    """项目对配置有明确偏离时（如“本项目只在 107 图执行安全阀直立”），把合并结果写成文件，各脚本照常按文件路径载入。
    文件里记录 overridden 与理由，不悄悄改变图面规则。返回文件路径字符串。"""
    P = merge(load(name), overrides)
    P['name'] = f"{P['name']}+项目覆盖"
    P['overridden'] = {'base': name, 'overrides': overrides, 'note': note}
    Path(out_file).write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding='utf-8')
    return str(out_file)


def sheet(P):
    s = P['sheet']
    return dict(s, frame=tuple(s['frame']), title_block=tuple(s['title_block']))
