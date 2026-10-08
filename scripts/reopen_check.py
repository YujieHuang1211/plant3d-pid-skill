"""重开核查：比对“全新 AutoCAD 会话中重新打开图纸后”PidBot info 导出的对象清单与绘图 spec。
用法: python reopen_check.py <info.log> <specs目录> <sheet> <输出.json>
  - spec 中每个带 id 的 asset/cv/line：其行号须出现在重开后的图纸里，位号与预期一致
"""
import json
import re
import sys
from pathlib import Path


def main(info, specdir, sheet, out):
    text = Path(info).read_text(encoding='utf-8')
    seen = {}
    for m in re.finditer(r'row=(\d+) class=(\S+) tag=(\S*)', text):
        seen[int(m.group(1))] = (m.group(2), m.group(3))
    specdir = Path(specdir)
    reg = json.loads((specdir / f'{sheet}.ids.json').read_text(encoding='utf-8'))
    spec = json.loads((specdir / f'{sheet}.json').read_text(encoding='utf-8'))
    fails, checks = [], 0
    for it in spec['items']:
        if it['k'] not in ('asset', 'cv', 'line') or not it.get('id'):
            continue
        checks += 1
        rid = reg.get(it['id'])
        if rid not in seen:
            fails.append(f"重开后图中无此对象 {it['id']} row={rid}")
            continue
        p = it.get('props', {})
        exp = None
        if 'Code' in p:
            exp = f"{p['Code']}-{p['Number']}"
        elif 'Type' in p and 'LoopNumber' in p:
            exp = f"{p['Type']}-{p['LoopNumber']}"
        elif 'Type' in p and 'Number' in p:
            exp = f"{p['Type']}-{p['Number']}"
        if it['k'] == 'line' and 'group' in it:
            g = it['group']
            exp = f"{g['Service']}-{g['LineNumber']}-{it['props']['Size']}-{it['props']['Spec']}"
        if exp and seen[rid][1] != exp:
            fails.append(f"重开后位号不符 {it['id']}: {seen[rid][1]} ≠ {exp}")
    r = {'sheet': sheet, 'info': str(info), 'objects_in_drawing': len(seen), 'checks': checks, 'fails': fails, 'pass': not fails}
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    print(('PASS' if not fails else 'FAIL'), sheet, 'checks', checks, 'fails', len(fails))
    for f in fails[:20]:
        print('  ', f)


if __name__ == '__main__':
    main(*sys.argv[1:5])
