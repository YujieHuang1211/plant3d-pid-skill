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
警告带稳定编号 [W-…]：W-FRAME-BOTTOM、W-NO-STYLE、W-OFF-PORT、W-TEXT-TEXT、W-TEXT-SYM、W-SYM-SYM。
  --block 编号,…   这些编号的警告若没被接受就算 ERROR（出图前必须处置）
  --accept 文件    已接受警告清单 JSON：[{"code": "W-TEXT-SYM", "match": "位号或图号片段", "reason": "理由", "sheet_sha": "该图 spec 的 sha256 前 12 位（可省）"}]；
                   图 spec 变了（sha 不符）清单即失效，需重新判断
符号几何来自 symbol_catalog.json（catalog_from_info.py 由实测 info 导出生成）。
"""
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402

TB = (235.0, 91.0)          # A3：标题栏+修订栏占 x>235、y<89（修订栏 3 行，留 2 mm）
FRAME = (25.0, 5.0, 415.0, 292.0)
TOL = 0.5
PSV_UPRIGHT = False          # True=全部图张；列表=只在这些图号上执行
DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / 'assets' / 'symbol_catalog.json'


def set_profile(name):
    """按制图配置设置图框、标题栏禁区和安全阀直立规则（缺省 legacy-2026-10 = 模块默认值）"""
    global FRAME, TB, PSV_UPRIGHT
    import drawprofile
    P = drawprofile.load(name)
    FRAME = tuple(float(v) for v in P['sheet']['frame'])
    TB = tuple(float(v) for v in P['sheet']['title_block'])
    PSV_UPRIGHT = P.get('psv_upright') or False
    return P


def is_psv(style):
    return ('Relief Valve' in style or 'Safety Valve' in style) and 'Rupture' not in style


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
    x1, y0 = x0 + w, top - h * (1 + 1.6 * (n - 1))     # 单行高 h，多行行距 1.6h
    ang = it.get('rot', 0) % 180
    if ang == 90:     # 竖排文字：绕插入点转 90°，外框宽高互换
        pts = [rot(px - x, py - y, 90) for px, py in ((x0, y0), (x1, y0), (x1, top), (x0, top))]
        return (x + min(p[0] for p in pts), x + max(p[0] for p in pts),
                y + min(p[1] for p in pts), y + max(p[1] for p in pts))
    return x0, x1, y0, top


def table_box(it):
    x, y = it['at']
    n = sum(max(c.count('\n') + 1 for c in r) for r in it['rows'])
    return x, x + sum(it['cols']), y - n * it['rowh'], y


def rot(dx, dy, ang):
    a = math.radians(ang)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def placed(cat, style, at, ang=0, scale=None, mirror=False):
    """符号实际外框与连接点（世界坐标，含旋转、比例、镜像）；目录无此样式返回 None。几何在 geometry.py"""
    return geometry.placed(cat, style, at, ang, scale, mirror)


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
                warns.append(f'[W-FRAME-BOTTOM] {no} 第 {n} 项 text 下沿距图框不足 5 mm（y={y0:.1f}）：注释太长时精简文字或上移起点（lint 估算偏小，实际更低）')
        if k == 'poly' and it.get('pts'):       # 转换后的折线也要在图框内、不进标题栏（普通图元版没有 Plant 的智能检查）
            xs, ys = [p[0] for p in it['pts']], [p[1] for p in it['pts']]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            if x0 < FRAME[0] - 0.01 or x1 > FRAME[2] + 0.01 or y0 < FRAME[1] - 0.01 or y1 > FRAME[3] + 0.01:
                errs.append(f'{no} 第 {n} 项 poly 超出图框：x {x0:.0f}~{x1:.0f}，y {y0:.0f}~{y1:.0f}')
            elif x1 > TB[0] and y0 < TB[1]:
                errs.append(f'{no} 第 {n} 项 poly 压标题栏/修订栏：x {x0:.0f}~{x1:.0f}，下沿 y={y0:.0f}')
        elif k == 'sym' and it.get('at'):
            sx, sy = it['at']
            if sx > TB[0] and sy < TB[1]:
                errs.append(f'{no} 第 {n} 项 sym 在标题栏/修订栏内：({sx:g},{sy:g})')
            elif not (FRAME[0] <= sx <= FRAME[2] and FRAME[1] <= sy <= FRAME[3]):
                errs.append(f'{no} 第 {n} 项 sym 插入点超出图框：({sx:g},{sy:g})')
        if it.get('id'):
            if it['id'] in here:
                errs.append(f'{no} 第 {n} 项 id 重复：{it["id"]}')
            here.add(it['id'])
            if k in ('asset', 'cv'):
                st = it.get('style') or it.get('body')
                if PSV_UPRIGHT and (PSV_UPRIGHT is True or no in PSV_UPRIGHT) and is_psv(st) and it.get('rot', 0) % 360:
                    errs.append(f'{no} {it["id"]}：安全阀“{st}”旋转了 {it["rot"]}°；按配置（PIP §4.2.1.16）安全阀须直立，不旋转符号凑空间，改支路或分图')
                pl = placed(cat, st, it['at'], it.get('rot', 0), it.get('scale'), it.get('mirror', False))
                if it.get('scale') is not None and (cat.get(st) or {}).get('plant_lib') and not geometry.factor(st, it['scale'])[1]:
                    errs.append(f'{no} {it["id"]}：Plant 库样式“{st}”没有默认比例记录（plant_style_scales.json），scale={it["scale"]} 无法换算，连接点会算错')
                if pl is None:
                    warns.append(f'[W-NO-STYLE] {no} {it["id"]}：目录无样式“{st}”，未检几何')
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
                warns.append(f'[W-OFF-PORT] {no} {it["line"]} {ctx} 端 ({p[0]:g},{p[1]:g}) 在 {it["asset"]} 上但不在连接点（最近 {d_att:.1f} mm）')
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
                warns.append(f'[W-TEXT-TEXT] {no} 文字第 {texts[i][0]} 项与第 {texts[j][0]} 项重叠')
    for n, tb in texts:
        for oid, (st, at, pl) in objs.items():
            if pl and st != 'nozzle':
                b = pl[0]
                if overlap(tb, (b[0], b[2], b[1], b[3])):
                    warns.append(f'[W-TEXT-SYM] {no} 文字第 {n} 项与 {oid} 符号重叠')
    # 符号与符号重叠（提示）：两个对象的外框互相压进去超过 1 mm（仪表圈标注、管嘴不算）
    boxes = [(oid, pl[0]) for oid, (st, at, pl) in objs.items() if pl and st != 'nozzle']
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a[0] < b[2] - 1.0 and b[0] < a[2] - 1.0 and a[1] < b[3] - 1.0 and b[1] < a[3] - 1.0:
                warns.append(f'[W-SYM-SYM] {no} {boxes[i][0]} 与 {boxes[j][0]} 符号外框重叠')
    return here


def classify(warns, errs, specdir, block, accept):
    """已接受的警告去掉；--block 里的编号若未被接受则升为 ERROR。返回 (warns, errs, 已接受条数)"""
    import hashlib
    sha = {}

    def sheet_sha(no):
        if no not in sha:
            f = Path(specdir) / f'{no}.json'
            sha[no] = hashlib.sha256(f.read_bytes()).hexdigest()[:12] if f.exists() else ''
        return sha[no]

    keep, n_acc = [], 0
    for w in warns:
        m = re.match(r'\[(W-[A-Z-]+)\] (P&ID-\w+)?', w)
        code, no = (m.group(1), m.group(2)) if m else (None, None)
        hit = next((a for a in accept if a.get('code') == code and a.get('match', '') in w and a.get('reason')
                    and (not a.get('sheet_sha') or a['sheet_sha'] == sheet_sha(no))), None)
        if hit:
            n_acc += 1
        elif code in block:
            errs = errs + [w + '（必须处置：改版面，或在 accepted_warnings.json 登记理由）']
        else:
            keep.append(w)
    return keep, errs, n_acc


def main(argv):
    args, cat_paths, strict, block, accept = [], [DEFAULT_CATALOG], False, set(), []
    i = 0
    while i < len(argv):
        if argv[i] == '--catalog':
            cat_paths.append(Path(argv[i + 1])); i += 2; continue
        if argv[i] == '--profile':
            set_profile(argv[i + 1]); i += 2; continue
        if argv[i] == '--block':
            block = set(x for x in argv[i + 1].split(',') if x); i += 2; continue
        if argv[i] == '--accept':
            accept = json.loads(Path(argv[i + 1]).read_text(encoding='utf-8')) if Path(argv[i + 1]).exists() else []
            i += 2; continue
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
    warns, errs, accepted = classify(warns, errs, specdir, block, accept)
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('WARN ', w)
    if accepted:
        print(f'INFO 已接受的警告 {accepted} 条（见 accepted_warnings.json）')
    ok = not errs and not (strict and warns)
    print('LINT', 'PASS' if ok else f'FAIL {len(errs)}', 'warn', len(warns), 'sheets', len(sheets))
    return ok


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
