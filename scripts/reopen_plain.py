"""普通图元 DWG 的重开核查：比对“全新 AutoCAD 会话重新打开后”info 导出的模型空间清单与普通版 spec。
用法: python reopen_plain.py <info.log> <普通版 specs 目录> <图号> <输出.json> [制图配置名]
检查（任一不符退出码 1）：
  1. 图纸确实打开并有内容
  2. 数量：文字（MText）、折线（Polyline，另有图框与标题栏 2 条，在“未打印”层）、块参照（BlockReference）与 spec 的 text / poly+rect / sym 一致；
     spec 里有 table 时表格生成的图元数未知，改为不少于
  3. spec 里每条文字都能在重开后的图里找到（按前 12 个字符匹配，MText 控制码忽略）
  4. 所有图元的图层都在 spec 声明的图层里（外加“未打印”）
  5. 所有图元外框都在图框内（配置的 sheet.frame），没有越界
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawprofile  # noqa: E402

EXT = re.compile(r'\[(-?[\d.]+),(-?[\d.]+)\]-\[(-?[\d.]+),(-?[\d.]+)\]')
ENT = re.compile(r'^(\w+) h=(\w+) layer=(\S+)')


def norm(s):
    s = re.sub(r'\\[LlPp]', '', str(s))
    s = re.sub(r'\\S([^;]*);', lambda m: m.group(1).replace('^', ''), s)
    s = re.sub(r'\\[A-Za-z][^;]*;', '', s)
    return re.sub(r'[{}\s]', '', s)


def parse_info(text):
    ents, opened = [], False
    for ln in text.splitlines():
        if ln.startswith('图纸:'):
            opened = True
            continue
        m = ENT.match(ln)
        if not m:
            continue
        e = {'type': m.group(1), 'layer': m.group(3)}
        x = EXT.search(ln)
        if x:
            e['box'] = tuple(float(v) for v in x.groups())
        t = re.search(r' mtext=(.*)$', ln)
        if t:
            e['text'] = norm(t.group(1))
        ents.append(e)
    return opened, ents


def check(info_text, spec_items, spec_layers, frame):
    opened, ents = parse_info(info_text)
    fails = []
    if not opened or not ents:
        return {'pass': False, 'fails': ['图纸没有打开或没有内容'], 'counts': {}}
    kinds = {}
    for it in spec_items:
        kinds[it['k']] = kinds.get(it['k'], 0) + 1
    has_table = bool(kinds.get('table'))
    got = {t: sum(1 for e in ents if e['type'] == t) for t in ('MText', 'Polyline', 'BlockReference')}
    want = {'MText': kinds.get('text', 0), 'Polyline': kinds.get('poly', 0) + kinds.get('rect', 0) + 2, 'BlockReference': kinds.get('sym', 0)}
    for t in got:
        bad = got[t] < want[t] if has_table else got[t] != want[t]
        if bad:
            fails.append(f'{t} 数量 {got[t]}，spec 应为 {want[t]}{"以上" if has_table else ""}')
    texts = [e['text'] for e in ents if 'text' in e]
    for it in spec_items:
        if it['k'] == 'text':
            key = norm(it['text'])[:12]
            if key and not any(t.startswith(key) or key.startswith(t[:12]) for t in texts):
                fails.append(f'重开后找不到文字：{key}')
    allowed = set(spec_layers) | {'未打印', '0'} | ({'表格'} if has_table else set())     # 表格对象由引擎放在“表格”层
    for lay in sorted({e['layer'] for e in ents} - allowed):
        fails.append(f'出现 spec 没有的图层：{lay}')
    x0, y0, x1, y1 = frame
    for e in ents:
        b = e.get('box')
        if b and (b[0] < x0 - 0.5 or b[1] < y0 - 0.5 or b[2] > x1 + 0.5 or b[3] > y1 + 0.5):
            fails.append(f'{e["type"]}（{e["layer"]}）越出图框：{b}')
    return {'pass': not fails, 'fails': fails, 'counts': {'got': got, 'want': want}}


def main(info, specdir, sheet, out, profile=None):
    P = drawprofile.load(profile)
    spec = json.loads((Path(specdir) / f'{sheet}.json').read_text(encoding='utf-8'))
    layers = {l['name'] for l in spec.get('layers', [])} | {it['layer'] for it in spec['items'] if it.get('layer')}
    r = check(Path(info).read_text(encoding='utf-8'), spec['items'], layers, drawprofile.sheet(P)['frame'])
    r.update(sheet=sheet, info=str(info))
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    print('REOPEN', 'PASS' if r['pass'] else f'FAIL {len(r["fails"])}', sheet, r['counts'])
    for f in r['fails'][:15]:
        print('  ', f)
    return r['pass']


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:6]) else 1)
