"""出图前静态检查 spec（不需要 AutoCAD）。
用法: python lint_specs.py <specs 目录> <图号 ...> [--catalog symbol_catalog.json ...] [--strict]
        （--catalog 可重复，后者覆盖前者；默认先载入技能自带目录）
ERROR（任一即 LINT FAIL）：
  - 引用未定义：connect/tee/nozzle 引用本图之前未定义的 id；opc 的 b 须在本图或同目录其他 spec 中定义
  - id 重复（本图内，以及同目录各图之间：引擎的对象登记按 id 全套共用，线 id 同名会让两张图的线并进同一线组）
  - 文字/表格压标题栏+修订栏（x>235、y<91）或超出图框
  - 连接几何：端接（start/end）线端离目标符号外框 >0.5 mm（图面看似未连上）；
    在线（inline）符号插入点不在管线上；三通（tee）线端不在被接管线上；接管嘴的线端离管嘴 >0.5 mm
WARN（不阻断；--strict 时也算失败）：
  - 线端落在符号外框内但不在连接点上
  - 文字与文字、文字与符号外框重叠
  - 目录中没有的样式（未检几何）
符号几何来自 symbol_catalog.json（catalog_from_info.py 由实测 info 导出生成）。
"""
import json
import math
import re
import sys
from pathlib import Path

TB = (235.0, 91.0)          # A3：标题栏+修订栏占 x>235、y<89（修订栏 3 行，留 2 mm）
FRAME = (25.0, 5.0, 415.0, 292.0)
TOL = 0.5
DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / 'assets' / 'symbol_catalog.json'


def text_box(it):
    """文字外框：字宽系数按出图实测（汉字 0.70h、西文 0.57h，MText 上下标代码不占宽）。"""
    x, y = it['at']
    h = it.get('h', 3.5)
    lines = [re.sub(r'\\S[^;]*;', '', ln) for ln in str(it.get('text', '')).split('\n')]
    w = max(sum(h * 0.70 if ord(c) > 0x2E80 else h * 0.57 for c in ln) for ln in lines)
    n = len(lines)
    just = it.get('just', 'ML')
    top = y if just.startswith('T') else y + h / 2 if just.startswith('M') else y + h
    x0 = x - w / 2 if just.endswith('C') else x - w if just.endswith('R') else x
    return x0, x0 + w, top - h * (1 + 1.6 * (n - 1)), top     # 单行高 h，多行行距 1.6h


def table_box(it):
    x, y = it['at']
    n = sum(max(c.count('\n') + 1 for c in r) for r in it['rows'])
    return x, x + sum(it['cols']), y - n * it['rowh'], y


def rot(dx, dy, ang):
    a = math.radians(ang)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def placed(cat, style, at, ang=0):
    """符号实际外框与连接点（世界坐标）；目录无此样式返回 None。"""
    c = cat.get(style)
    if not c:
        return None
    x0, y0, x1, y1 = c['bbox']
    cs = [rot(dx, dy, ang) for dx, dy in ((x0, y0), (x1, y1), (x0, y1), (x1, y0))]
    box = (at[0] + min(p[0] for p in cs), at[1] + min(p[1] for p in cs), at[0] + max(p[0] for p in cs), at[1] + max(p[1] for p in cs))
    att = [(at[0] + rot(dx, dy, ang)[0], at[1] + rot(dx, dy, ang)[1]) for dx, dy in c['att']]
    return box, att


def dist_box(p, b):
    dx = max(b[0] - p[0], 0, p[0] - b[2])
    dy = max(b[1] - p[1], 0, p[1] - b[3])
    return math.hypot(dx, dy)


def dist_seg(p, a, b):
    ax, ay, bx, by = *a, *b
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L))
    return math.hypot(p[0] - ax - t * vx, p[1] - ay - t * vy)


def dist_poly(p, pts):
    return min(dist_seg(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1)) if len(pts) > 1 else math.inf


def overlap(a, b, pad=0.2):
    """a、b 为 (x0, x1, y0, y1)"""
    return a[0] < b[1] - pad and b[0] < a[1] - pad and a[2] < b[3] - pad and b[2] < a[3] - pad


REFS = {'connect': ('line', 'asset'), 'tee': ('line', 'to'), 'opc': ('a', 'b'), 'nozzle': ('on',)}


def lint_sheet(no, items, cat, all_ids, errs, warns):
    here, objs, lines = set(), {}, {}
    for n, it in enumerate(items):
        k = it['k']
        for key in REFS.get(k, ()):
            ref = it.get(key)
            ok = ref in here or (k == 'opc' and key == 'b' and ref in all_ids)
            if not ok:
                errs.append(f'{no} 第 {n} 项 {k}.{key}={ref}：引用前未定义')
        if k in ('table', 'text'):
            x0, x1, y0, y1 = table_box(it) if k == 'table' else text_box(it)
            if x1 > TB[0] and y0 < TB[1]:
                errs.append(f'{no} 第 {n} 项 {k} 压标题栏/修订栏：x {x0:.0f}~{x1:.0f}，下沿 y={y0:.0f}')
            if x0 < FRAME[0] or x1 > FRAME[2] or y0 < FRAME[1] or y1 > FRAME[3]:
                errs.append(f'{no} 第 {n} 项 {k} 超出图框：x {x0:.0f}~{x1:.0f}，y {y0:.0f}~{y1:.0f}')
            elif y0 < FRAME[1] + 5 and k == 'text':
                warns.append(f'{no} 第 {n} 项 text 下沿距图框不足 5 mm（y={y0:.1f}）：注释太长时精简文字或上移起点（lint 估算偏小，实际更低）')
        if it.get('id'):
            if it['id'] in here:
                errs.append(f'{no} 第 {n} 项 id 重复：{it["id"]}')
            here.add(it['id'])
            if k in ('asset', 'cv'):
                st = it.get('style') or it.get('body')
                pl = placed(cat, st, it['at'], it.get('rot', 0))
                if pl is None:
                    warns.append(f'{no} {it["id"]}：目录无样式“{st}”，未检几何')
                objs[it['id']] = (st, it['at'], pl)
            elif k == 'nozzle':
                p = tuple(it['at'])
                objs[it['id']] = ('nozzle', p, ((p[0], p[1], p[0], p[1]), [p]))
            elif k == 'line':
                lines[it['id']] = it['pts']

    # ---- 连接几何
    for it in items:
        if it['k'] == 'connect' and it['line'] in lines and it['asset'] in objs:
            pts = lines[it['line']]
            st, at, pl = objs[it['asset']]
            ctx = it.get('ctx', 'inline')
            if ctx == 'inline':
                d = dist_poly(at, pts)
                if d > TOL:
                    errs.append(f'{no} {it["asset"]} 在线符号不在管线 {it["line"]} 上（偏 {d:.1f} mm）')
                continue
            if pl is None:
                continue
            p = pts[0] if ctx == 'start' else pts[-1]
            box, att = pl
            d_att = min((math.hypot(p[0] - a[0], p[1] - a[1]) for a in att), default=math.inf)
            d_box = dist_box(p, box)
            if d_att <= TOL:
                continue
            if d_box > TOL:
                errs.append(f'{no} {it["line"]} {ctx} 端 ({p[0]:g},{p[1]:g}) 离 {it["asset"]} 外框 {d_box:.1f} mm，图面未连上')
            elif att:
                warns.append(f'{no} {it["line"]} {ctx} 端 ({p[0]:g},{p[1]:g}) 在 {it["asset"]} 上但不在连接点（最近 {d_att:.1f} mm）')
        elif it['k'] == 'tee' and it['line'] in lines and it['to'] in lines:
            pts = lines[it['line']]
            p = pts[0] if it.get('start', True) else pts[-1]
            d = dist_poly(p, lines[it['to']])
            if d > TOL:
                errs.append(f'{no} 三通 {it["line"]} 线端 ({p[0]:g},{p[1]:g}) 不在管线 {it["to"]} 上（偏 {d:.1f} mm）')

    # ---- 重叠（提示）
    texts = [(n, text_box(it)) for n, it in enumerate(items) if it['k'] == 'text']
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if overlap(texts[i][1], texts[j][1]):
                warns.append(f'{no} 文字第 {texts[i][0]} 项与第 {texts[j][0]} 项重叠')
    for n, tb in texts:
        for oid, (st, at, pl) in objs.items():
            if pl and st != 'nozzle':
                b = pl[0]
                if overlap(tb, (b[0], b[2], b[1], b[3])):
                    warns.append(f'{no} 文字第 {n} 项与 {oid} 符号重叠')
    return here


def main(argv):
    args, cat_paths, strict = [], [DEFAULT_CATALOG], False
    i = 0
    while i < len(argv):
        if argv[i] == '--catalog':
            cat_paths.append(Path(argv[i + 1])); i += 2; continue
        if argv[i] == '--strict':
            strict = True; i += 1; continue
        args.append(argv[i]); i += 1
    specdir, sheets = Path(args[0]), args[1:]
    cat = {}
    for cp in cat_paths:
        if cp.exists():
            cat.update(json.loads(cp.read_text(encoding='utf-8')))
    all_ids, owner, errs, warns = set(), {}, [], []
    for f in sorted(specdir.glob('*.json')):
        if f.name.endswith(('.props.json', '.ids.json')) or f.stem.startswith('_'):
            continue
        try:
            ids = {it['id'] for it in json.loads(f.read_text(encoding='utf-8')).get('items', []) if it.get('id')}
        except (json.JSONDecodeError, AttributeError):
            continue
        all_ids |= ids
        for i_ in ids:
            owner.setdefault(i_, []).append(f.stem)
    for i_, fs in sorted(owner.items()):
        if len(fs) > 1 and any(s in sheets for s in fs):
            errs.append(f'id 跨图重复：{i_} 同时出现在 {"、".join(fs)}（线 id、对象 id 须全套唯一，否则线组串组、位号错乱）')
    for no in sheets:
        items = json.loads((specdir / f'{no}.json').read_text(encoding='utf-8'))['items']
        lint_sheet(no, items, cat, all_ids, errs, warns)
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('WARN ', w)
    ok = not errs and not (strict and warns)
    print('LINT', 'PASS' if ok else f'FAIL {len(errs)}', 'warn', len(warns), 'sheets', len(sheets))
    return ok


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
