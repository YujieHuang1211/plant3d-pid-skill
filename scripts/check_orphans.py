"""Plant 项目库残留检查（只读，读 dcf 副本）：
  - 空线组：PipeLineGroup / SignalLineGroup 中没有任何成员线的行（删图重画后残留，新线号会带“?”）
  - 孤立位号登记：PnPTagRegistry 中 RowId 既不在 PnPDataLinks（图上对象）也不是线组行的登记（闪退后残留，重画位号会带“?”）
用法: python check_orphans.py <ProcessPower.dcf> [输出.json]
退出码 0＝无残留，1＝有残留。
"""
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def load(dcf):
    tmp = Path(tempfile.mkdtemp()) / 'pp.dcf'
    shutil.copy2(dcf, tmp)
    return sqlite3.connect(tmp)


def tables(c):
    return {r[0] for r in c.execute("select name from sqlite_master where type='table'")}


def main(dcf, out=None):
    c = load(dcf)
    ts = tables(c)
    groups, members = {}, {}
    for g in ('PipeLineGroup', 'SignalLineGroup'):
        if g in ts:
            for (pid,) in c.execute(f'select PnPID from "{g}"'):
                groups[pid] = g
    # 线组—成员关系表：列名含线组表名（PipeLineGroupRelationship: PipeLineGroup, PipeLine）
    for t in ts:
        cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
        for g in ('PipeLineGroup', 'SignalLineGroup'):
            if t != g and g in cols and len(cols) >= 2:
                other = [x for x in cols if x not in ('PnPID', 'PnPGuid', 'PnPTimestamp', g)]
                if other:
                    for gid, mid in c.execute(f'select "{g}", "{other[0]}" from "{t}"'):
                        members.setdefault(gid, set()).add(mid)
    linked = {r[0] for r in c.execute('select RowId from PnPDataLinks')}
    empty = sorted(gid for gid in groups if not (members.get(gid, set()) & linked))
    dangling = []
    if 'PnPTagRegistry' in ts:
        for tag, rid in c.execute('select Tag, RowId from PnPTagRegistry'):
            if rid not in linked and rid not in groups:
                dangling.append([tag, rid])
    res = {'empty_line_groups': [[g, groups[g]] for g in empty], 'dangling_tag_registry': dangling,
           'pass': not empty and not dangling}
    if out:
        Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(('ORPHANS PASS' if res['pass'] else 'ORPHANS FAIL'), 'empty_groups', len(empty), 'dangling_tags', len(dangling))
    for g in empty[:10]:
        print('  空线组', g, groups[g])
    for d in dangling[:10]:
        print('  孤立位号登记', d)
    return res['pass']


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:3]) else 1)
