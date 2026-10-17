"""线号自动排布：把没有线号的管线补上，把压在别的东西上的线号换到空位。

在项目 sheets.py 里，每张图 dump 之后、写文件之前，对 spec 调用 autolabel.autolabel(spec)（需把本脚本目录放进 sys.path）。做法：
1. 去掉所有线号标注后，把图转成普通图元（与出图时同一套转换），得到文字、符号、折线、表格等障碍物；
2. 对每条管线逐个找位置：先试手工给定的位置，不行就沿管线每隔 2 mm 取候选点（线上方/下方，竖线左/右），
   取第一个与全部障碍物和已放置线号都不相交的点；
3. 同一线号在同一张图上只标一处（支线沿用主管线号，不重复标）。
"""
import copy
import json
import math
import sys
from pathlib import Path

SK = Path.home() / '.claude' / 'skills' / 'plant3d-pid' / 'scripts'
sys.path.insert(0, str(SK))
import plain_convert as pc          # noqa: E402
from lint_specs import FRAME, TB, text_box, table_box, rot as _rot   # noqa: E402

H = 2.5
CW, AW = 0.70, 0.57
OFF_ON = 0.9       # 与 plain_convert 保持一致：线上标注，文字距线 OFF_V（竖）或 OFF_H（横）
_cat = None


def catalog():
    global _cat
    if _cat is None:
        _cat = json.loads((SK.parent / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))
    return _cat


def label_text(g):
    return '-'.join(str(g.get(k, '')) for k in ('Service', 'LineNumber', 'NominalSize', 'NominalSpec'))


def label_w(txt):
    return sum(H * (CW if ord(c) > 0x2E80 else AW) for c in txt)


def sym_box(it, conv):
    st = it.get('style')
    c = conv.cat.get(st) or {}
    bb = c.get('bbox') or [-4, -2, 4, 2]
    f = 1.0
    if 'scale' in it:
        if (pc.GEOM.get(st) or {}).get('native'):
            f = float(it['scale'])
        else:
            f = float(it['scale']) / float((pc.STYLE_SCALES.get(st) or {}).get('scale') or it['scale'])
    x0, y0, x1, y1 = (v * f for v in bb)
    r = it.get('rot', 0)
    cs = [_rot(dx, dy, r) for dx, dy in ((x0, y0), (x1, y1), (x0, y1), (x1, y0))]
    x, y = it['at']
    return (x + min(p[0] for p in cs), x + max(p[0] for p in cs), y + min(p[1] for p in cs), y + max(p[1] for p in cs))


def seg_hits_rect(a, b, r, pad=0.0):
    """线段 ab 是否与矩形 r=(x0,x1,y0,y1) 相交（Liang–Barsky）"""
    x0, x1, y0, y1 = r[0] - pad, r[1] + pad, r[2] - pad, r[3] + pad
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return t0 <= t1


def rect_overlap(a, b, pad=0.3):
    return a[0] < b[1] + pad and b[0] < a[1] + pad and a[2] < b[3] + pad and b[2] < a[3] + pad


def dist_seg(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L = vx * vx + vy * vy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def on_path(p, V, tol=0.35):
    return any(dist_seg(p, V[i], V[i + 1]) < tol for i in range(len(V) - 1))


def build_obstacles(items, conv):
    plain = conv.convert(copy.deepcopy(items))
    rects, segs = [], []
    for it in plain:
        k = it['k']
        if k == 'text':
            rects.append(text_box(it))
        elif k == 'sym':
            if (it.get('style') or '') == pc.ARROW_STYLE:
                x, y = it['at']
                rects.append((x - 2.5, x + 2.5, y - 2.5, y + 2.5))
            else:
                rects.append(sym_box(it, conv))
        elif k == 'table':
            rects.append(table_box(it))
        elif k == 'poly':
            pts = it['pts']
            for i in range(len(pts) - 1):
                segs.append((pts[i], pts[i + 1]))
    return rects, segs


def candidates(V, w):
    """沿折线生成候选 (anno 点, 文字外框)；先线上方/左侧，再下方/右侧"""
    out = []
    for i in range(len(V) - 1):
        a, b = V[i], V[i + 1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-6:
            continue
        horiz = abs(b[1] - a[1]) < abs(b[0] - a[0])
        # 文字沿线方向需要的长度
        if L < w + 3.0:
            continue
        n = int((L - w - 3.0) / 2.0) + 1
        mid = L / 2
        ts = sorted([1.5 + w / 2 + 2.0 * j for j in range(n + 1)], key=lambda t: abs(t - mid))
        for t in ts:
            if t - w / 2 < 1.0 or t + w / 2 > L - 1.0:
                continue
            x = a[0] + (b[0] - a[0]) * t / L
            y = a[1] + (b[1] - a[1]) * t / L
            if horiz:
                out.append(([round(x, 2), round(y, 2)], (x - w / 2, x + w / 2, y + pc.OFF_H, y + pc.OFF_H + H)))
                out.append(([round(x, 2), round(y - 2.5, 2)], (x - w / 2, x + w / 2, y - 2.5 - H / 2, y - 2.5 + H / 2)))
            else:
                out.append(([round(x, 2), round(y, 2)], (x - pc.OFF_V - H, x - pc.OFF_V, y - w / 2, y + w / 2)))
                out.append(([round(x + 2.5, 2), round(y, 2)], (x + 2.5 - H / 2, x + 2.5 + H / 2, y - w / 2, y + w / 2)))
    return out


def manual_box(V, an, w):
    """按 plain_convert 的规则算手工标注点对应的文字外框"""
    best, bd = None, 1e9
    for i in range(len(V) - 1):
        d = dist_seg(an, V[i], V[i + 1])
        if d < bd:
            best, bd = i, d
    a, b = V[best], V[best + 1]
    vertical = abs(b[0] - a[0]) < abs(b[1] - a[1])
    x, y = an
    if bd < pc.ON_LINE:
        if vertical:
            return (x - pc.OFF_V - H, x - pc.OFF_V, y - w / 2, y + w / 2)
        return (x - w / 2, x + w / 2, y + pc.OFF_H, y + pc.OFF_H + H)
    if vertical:
        return (x - H / 2, x + H / 2, y - w / 2, y + w / 2)
    return (x - w / 2, x + w / 2, y - H / 2, y + H / 2)


def autolabel(spec, only_missing_unique=True):
    items = spec['items']
    conv = pc.Conv(catalog())
    base = copy.deepcopy(items)
    for it in base:
        if it['k'] == 'line':
            it.pop('anno', None)
    rects, segs = build_obstacles(base, conv)
    frame = [(-50, FRAME[0], -50, 400), (FRAME[2], 500, -50, 400), (-50, 500, -50, FRAME[1]), (-50, 500, FRAME[3], 400)]
    fixed = rects + frame + [(TB[0], 500, -50, TB[1])]
    placed_boxes, labelled = [], {}
    stats = {'kept': 0, 'moved': 0, 'added': 0, 'fail': []}

    def free(box, V, boxes):
        e = (box[0] - 0.4, box[1] + 0.4, box[2] - 0.4, box[3] + 0.4)
        if any(rect_overlap(box, r, 0.4) for r in fixed) or any(rect_overlap(box, r, 0.4) for r in boxes):
            return False
        for a, b in segs:
            if on_path(a, V) and on_path(b, V):
                continue                    # 本线自身的线段
            if seg_hits_rect(a, b, e):
                return False
        return True

    lines = [it for it in items if it['k'] == 'line' and it.get('group')]
    # 先处理已有手工标注的线，再补没有标注的线
    order = [it for it in lines if it.get('anno')] + [it for it in lines if not it.get('anno')]
    for it in order:
        txt = label_text(it['group'])
        w = label_w(txt)
        V = it['pts']
        if txt in labelled and not it.get('anno'):
            continue                        # 支线沿用主线号
        if txt in labelled and it.get('anno'):
            stats['kept'] += 0
        manual = it.get('anno')
        if manual:
            bx = manual_box(V, manual, w)
            if free(bx, V, placed_boxes):
                placed_boxes.append(bx)
                labelled[txt] = True
                stats['kept'] += 1
                continue
        for an, bx in candidates(V, w):
            if free(bx, V, placed_boxes):
                it['anno'] = an
                placed_boxes.append(bx)
                labelled[txt] = True
                stats['moved' if manual else 'added'] += 1
                break
        else:
            if manual:
                bx = manual_box(V, manual, w)
                placed_boxes.append(bx)
                labelled[txt] = True
            stats['fail'].append((it['id'], txt, bool(manual)))
    return stats


if __name__ == '__main__':
    p = Path(sys.argv[1])
    d = json.loads(p.read_text(encoding='utf-8'))
    print(autolabel(d))
