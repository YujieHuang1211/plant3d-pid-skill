"""P&ID 连接与属性核查：读 Plant 项目库 ProcessPower.dcf 的副本，对照 PidBot 绘图 spec 逐项核对。
用法: python verify_topology.py <ProcessPower.dcf> <specs目录> <输出.json> [sheet ...]
  - spec 中每个 connect/tee/opc 项 → 必须在库中有对应关系（内联/起点/终点/线-线/跨图配对）
  - 每个带位号对象 → 库中位号非空、与 spec 预期一致；全项目位号唯一（线组位号按 LineNumber）
  - 关键智能属性（Description、BasisRef 等）非空
只读：先把 dcf 复制到临时文件再打开，不改项目库。
"""
import json
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

REL = {'inline': 'LineInlineAsset', 'start': 'LineStartAsset', 'end': 'LineEndAsset'}


def load_db(dcf):
    tmp = Path(tempfile.mkdtemp()) / 'pp.dcf'
    shutil.copy2(dcf, tmp)
    return sqlite3.connect(tmp)


def tables(c):
    return {r[0] for r in c.execute("select name from sqlite_master where type='table'")}


def rel_pairs(c, t, a='Line', b='Asset'):
    if t not in tables(c):
        return set()
    return {(r[0], r[1]) for r in c.execute(f'select "{a}","{b}" from "{t}"')}


def tag_map(c):
    """行号 → (表, 位号)；遍历所有含 Tag 列的类表"""
    out = {}
    for t in tables(c):
        cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
        if 'Tag' in cols and 'PnPID' in cols and t not in ('PnPTagRegistry', 'Nozzles', 'AssumedNozzle', 'FlangedNozzle'):   # 位号登记表不是对象；管嘴编号按设备各自编
            for pid, tag in c.execute(f'select PnPID, Tag from "{t}"'):
                if tag:
                    out.setdefault(pid, (t, tag))
    return out


def props(c, pid, names):
    got = {}
    for t in tables(c):
        cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
        want = [n for n in names if n in cols]
        if want and 'PnPID' in cols:
            row = c.execute(f'select {",".join(chr(34)+w+chr(34) for w in want)} from "{t}" where PnPID=?', (pid,)).fetchone()
            if row:
                for w, v in zip(want, row):
                    if v not in (None, ''):
                        got[w] = v
    return got


def main(dcf, specdir, out, sheets):
    c = load_db(dcf)
    specdir = Path(specdir)
    reg = {}
    for f in specdir.glob('*.ids.json'):
        reg.update(json.loads(f.read_text(encoding='utf-8')))
    rels = {k: rel_pairs(c, t) for k, t in REL.items()}
    opc = rel_pairs(c, 'LineOffPageConnector', 'Line', 'OffPageConnector')   # 线-跨图连接器单独成表
    opc |= rel_pairs(c, 'LineNozzle', 'Line', 'Nozzle')                      # 线-管嘴也单独成表
    opc_pair = rel_pairs(c, 'ConnectorsRelationship', 'Connector1', 'Connector2')   # 跨图连接器配对
    ls = rel_pairs(c, 'LineStartLine', 'Line1', 'Line2')
    le = rel_pairs(c, 'LineEndLine', 'Line1', 'Line2')
    alive = {r[0] for r in c.execute('select PnPID from PnPBase')} if 'PnPBase' in tables(c) else set()
    tags = tag_map(c)
    result = {'dcf': str(dcf), 'sheets': {}, 'summary': {}}
    total_fail = 0
    for sh in sheets:
        spec = json.loads((specdir / f'{sh}.json').read_text(encoding='utf-8'))
        fails, checks = [], 0
        for it in spec['items']:
            k = it['k']
            if k == 'connect':
                checks += 1
                ln, asset = reg.get(it['line']), reg.get(it['asset'])
                if ln is None or asset is None:
                    fails.append(f"未登记 {it['line']}/{it['asset']}")
                    continue
                if (ln, asset) not in rels[it['ctx']] and (ln, asset) not in opc:
                    fails.append(f"缺关系 {it['ctx']}: {it['line']}({ln}) – {it['asset']}({asset})")
            elif k == 'opc':
                checks += 1
                a, b = reg.get(str(it['a'])), reg.get(str(it['b']))
                if a is None or b is None:
                    fails.append(f"未登记连接器 {it['a']}/{it['b']}")
                elif (a, b) not in opc_pair and (b, a) not in opc_pair:
                    fails.append(f"跨图连接器未配对 {it['a']}({a}) ↔ {it['b']}({b})")
            elif k == 'tee':
                checks += 1
                a, b = reg.get(it['line']), reg.get(it['to'])
                if a is None or b is None:
                    fails.append(f"未登记 tee {it['line']}/{it['to']}")
                    continue
                if (a, b) not in (ls if it.get('start', True) else le):
                    fails.append(f"缺三通 {'起点' if it.get('start', True) else '终点'}: {it['line']} → {it['to']}")
            elif k in ('asset', 'cv', 'line') and it.get('id'):
                rid = reg.get(it['id'])
                checks += 1
                if rid is None or (alive and rid not in alive):
                    fails.append(f"对象不在库中 {it['id']}")
                    continue
                exp = None
                p = it.get('props', {})
                if 'Code' in p:
                    exp = f"{p['Code']}-{p['Number']}"
                elif 'Type' in p and 'LoopNumber' in p:
                    exp = f"{p['Type']}-{p['LoopNumber']}"
                elif 'Type' in p and 'Number' in p:
                    exp = f"{p['Type']}-{p['Number']}"
                if k == 'line' and 'group' in it:
                    g = it['group']
                    exp = f"{g['Service']}-{g['LineNumber']}-{it['props']['Size']}-{it['props']['Spec']}"
                if exp:
                    got = tags.get(rid, (None, None))[1]
                    if got != exp:
                        fails.append(f"位号不符 {it['id']}: 库中={got} 预期={exp}")
                if k in ('asset', 'cv') and p.get('Description'):
                    pr = props(c, rid, ['Description', 'BasisRef'])
                    if 'Description' not in pr:
                        fails.append(f"属性缺失 {it['id']}: Description")
        result['sheets'][sh] = {'checks': checks, 'fails': fails, 'pass': not fails}
        total_fail += len(fails)
    # 全项目位号唯一（管线段位号同线号多段属正常，排除 PipeLines/线组）
    dup = [t for t, n in Counter(v[1] for v in tags.values() if v[0] not in ('PipeLines', 'Primary', 'Secondary', 'PipeLineGroup', 'Lines') and '?' not in v[1]).items() if n > 1]
    result['summary'] = {'fails': total_fail, 'duplicate_tags': dup, 'pass': total_fail == 0 and not dup}
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print('PASS' if result['summary']['pass'] else 'FAIL', 'fails=', total_fail, 'dup=', dup[:10])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
