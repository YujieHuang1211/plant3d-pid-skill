"""检查点（项目 zip 备份）的身份清单与恢复前校验，供引擎 build_set.ps1 调用（也可单独用）。
  python ckpt.py write  <zip> <specs 目录> --sheets 图号,图号 [--run-id 编号] [--phase 说明]
        在 <zip>.manifest.json 里记：运行编号、已完成图张、这些图的 spec 哈希、zip 的哈希
  python ckpt.py dbcopy <项目目录> <临时目录>
        把项目里的 SQLite 库（*.dcf）用在线备份接口复制成一致的副本（AutoCAD 打开着也可读，2026-10-20 实测）；
        打 zip 时用副本代替原文件，避免备份到写了一半的库。其余文件照常复制
  python ckpt.py verify <zip> <specs 目录>
        恢复前校验：zip 能完整打开、清单在、清单里已完成图张的 spec 哈希与现在一致、zip 哈希没变。不符退出码 1 并说明原因，
        恢复方不得继续（输入变了的旧图不能混进新版本）
spec 哈希的算法与 plain_pipeline.input_hashes 一致（<图号>.json + <图号>.props.json）。
"""
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path


def spec_hash(specs, no):
    h = hashlib.sha256()
    for suf in ('.json', '.props.json'):
        f = Path(specs) / f'{no}{suf}'
        h.update(f.read_bytes() if f.exists() else b'')
    return h.hexdigest()[:16]


def zip_sha(zpath):
    h = hashlib.sha256()
    with open(zpath, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()[:16]


def manifest_file(zpath):
    return Path(str(zpath) + '.manifest.json')


def write(zpath, specs, sheets, run_id='', phase=''):
    m = {'run_id': run_id, 'phase': phase, 'created': time.time(), 'sheets_done': list(sheets),
         'specs': {n: spec_hash(specs, n) for n in sheets}, 'zip_sha': zip_sha(zpath)}
    manifest_file(zpath).write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')
    return m


def verify(zpath, specs):
    """返回问题列表，空表示可以恢复"""
    zpath = Path(zpath)
    if not zpath.exists():
        return [f'检查点 {zpath.name} 不存在']
    try:
        with zipfile.ZipFile(zpath) as z:
            bad = z.testzip()
        if bad:
            return [f'检查点 {zpath.name} 损坏：{bad}']
    except zipfile.BadZipFile:
        return [f'检查点 {zpath.name} 不是完整的 zip']
    mf = manifest_file(zpath)
    if not mf.exists():
        return [f'检查点 {zpath.name} 没有身份清单（旧版备份），无法确认与当前输入一致']
    m = json.loads(mf.read_text(encoding='utf-8'))
    out = []
    if m.get('zip_sha') != zip_sha(zpath):
        out.append(f'检查点 {zpath.name} 的哈希与清单不符，可能被改动')
    for n, h in m.get('specs', {}).items():
        if spec_hash(specs, n) != h:
            out.append(f'{n} 的 spec 在检查点之后变了，不能沿用该检查点里的旧图')
    return out


def dbcopy(prj, out):
    """项目目录下每个 *.dcf 用 sqlite3 在线备份接口复制到 out（保持相对路径）。返回 [(相对路径, 是否成功, 说明)]"""
    import sqlite3
    prj, out = Path(prj), Path(out)
    res = []
    for f in sorted(prj.rglob('*.dcf')):
        rel = f.relative_to(prj)
        dst_path = out / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            src = sqlite3.connect(f'file:{f.as_posix()}?mode=ro', uri=True, timeout=5)
            dst = sqlite3.connect(dst_path)
            src.backup(dst)
            ok = dst.execute('pragma integrity_check').fetchone()[0] == 'ok'
            dst.close()
            src.close()
            res.append((str(rel), ok, 'ok' if ok else '副本完整性检查未通过'))
        except Exception as e:
            res.append((str(rel), False, f'{type(e).__name__}: {e}'))
    return res


def main(argv):
    if len(argv) < 3 or argv[0] not in ('write', 'verify', 'dbcopy'):
        print(__doc__)
        return 2
    if argv[0] == 'dbcopy':
        bad = [r for r in dbcopy(argv[1], argv[2]) if not r[1]]
        for r in bad:
            print('CKPT DB FAIL', *r)
        print('CKPT DBCOPY', 'OK' if not bad else 'FAIL')
        return 0 if not bad else 1
    cmd, zpath, specs = argv[0], argv[1], argv[2]
    opt = {argv[i]: argv[i + 1] for i in range(3, len(argv) - 1, 2)}
    if cmd == 'write':
        m = write(zpath, specs, [s for s in opt.get('--sheets', '').split(',') if s], opt.get('--run-id', ''), opt.get('--phase', ''))
        print('CKPT WRITE', Path(zpath).name, len(m['sheets_done']), '张')
        return 0
    problems = verify(zpath, specs)
    for p in problems:
        print('CKPT FAIL', p)
    print('CKPT', 'OK' if not problems else 'REFUSED')
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
