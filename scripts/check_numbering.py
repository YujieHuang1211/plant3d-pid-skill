"""编号与交叉引用核查（出图前，离线）：
用法: python check_numbering.py <pid_model.json> <普通版 specs 目录>
检查：
  1. 线号 物料-主项序号-外径-等级：每个主项（序号前两位）内序号从 01 起连续，没有缺号、重号
  2. 联锁编号 I-xx 从 I-01 起连续；图上文字里出现的 I-xx 都在模型里
  3. 图上文字里出现的位号（如 XV-261、PCV-104、E-101）都在模型里（设备、在线件、仪表、界区）——
     删了元件却漏改注释、联锁表、图例时在这里报出
  4. 同一回路号的一组仪表是否成套：流量控制器 FIC-xyz 的 PCV、PI、XV 同号（警告）
退出码：无 ERROR 为 0。
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def strip(s):
    s = re.sub(r'\\[LlPp]', '', s)
    s = re.sub(r'\\S([^;]*);', lambda m: m.group(1).replace('^', ''), s)
    return re.sub(r'\\[A-Za-z][^;]*;', '', s)


def main(model, specs):
    M = json.loads(Path(model).read_text(encoding='utf-8'))
    errs, warns = [], []
    # 1. 线号
    groups = defaultdict(list)
    seen = {}
    for l in M['lines']:
        p = l['no'].split('-')
        seq = p[1]
        if seq in seen:
            errs.append(f'线号序号重复：{seen[seq]} 与 {l["no"]}')
        seen[seq] = l['no']
        groups[seq[:2]].append(int(seq[2:]))
    for g, v in sorted(groups.items()):
        exp = list(range(1, len(v) + 1))
        if sorted(v) != exp:
            miss = sorted(set(exp) - set(v))
            errs.append(f'主项 {g} 的线号序号不连续：已有 {sorted(v)}，缺 {miss}')
    # 2. 联锁
    ids = [i['id'] for i in M.get('interlocks', [])]
    want = [f'I-{k:02d}' for k in range(1, len(ids) + 1)]
    if sorted(ids) != want:
        errs.append(f'联锁编号不连续：{sorted(ids)}')
    # 3. 位号引用
    tags = set()
    for k in ('equipment', 'inline', 'instruments', 'boundary'):
        for x in M.get(k, []):
            tags.add(x.get('tag') or x.get('id'))
    pat = re.compile(r'(?<![A-Za-z0-9&])([A-Z]{1,4}-\d{3}[A-Z]?)(?![A-Za-z0-9])')
    for f in sorted(Path(specs).glob('P&ID-*.json')):
        if f.name.endswith(('.props.json', '.ids.json')):
            continue
        for it in json.loads(f.read_text(encoding='utf-8'))['items']:
            if it['k'] != 'text':
                continue
            t = strip(it['text']).replace(chr(10), '')
            for m in pat.finditer(t):
                tag = m.group(1)
                if tag.startswith('P&') or re.match(r'(CO2|H2|PG|SG|TG|VT|DR|MG|CWS|CWR|FG)-', tag):
                    continue
                if tag.startswith('I-'):
                    continue
                if tag not in tags:
                    errs.append(f'{f.stem} 文字里的位号 {tag} 不在模型里：{t[:30].strip()}…')
            for m in re.finditer(r'(?<![A-Za-z0-9])(I-\d\d)(?![A-Za-z0-9])', t):
                if m.group(1) not in ids:
                    errs.append(f'{f.stem} 文字里的联锁 {m.group(1)} 不在模型里：{t[:30].strip()}…')
    # 4. 回路成套
    for t in sorted(tags):
        m = re.match(r'FIC-(\d{3})$', t or '')
        if m:
            n = m.group(1)
            for pre in ('PCV', 'PI', 'XV'):
                if f'{pre}-{n}' not in tags:
                    warns.append(f'FIC-{n} 没有同号的 {pre}-{n}')
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('WARN ', w)
    print('NUMBERING', 'PASS' if not errs else f'FAIL {len(errs)}', 'warn', len(warns))
    return not errs


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:3]) else 1)
