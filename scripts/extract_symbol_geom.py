"""从符号图集 PDF 的矢量路径里提取每个符号的几何，存成“非智能对象”的几何库（普通折线，与 Plant 无关）。
用法: python extract_symbol_geom.py <图集 PDF 目录> <图集 spec 目录> <输出 geom 目录> [--report]
  - 图集 PDF 由 build_set 画出（SYM-ATLAS-nn.pdf）；图集 spec 目录里有每个符号的插入点和缩放
  - 输出 <geom 目录>/plant_symbols_geom.json：{样式名: {"paths": [{"pts": [[x,y],…], "closed": bool, "fill": bool}], "bbox": […], "n": 路径数}}
    坐标 = 相对插入点的 mm，比例 1（已除去图集里的缩放）
  - 画出来只有一个点或几乎没有线的符号（Plant 设备类样式，块里没有几何，由 Plant 运行时生成）记为 "dot": true，
    它们不能直接当普通块用，需要另行手工定义几何（见 symbol_geom.py）
"""
import json
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from symbol_atlas import style_scale  # noqa: E402

PT2MM = 25.4 / 72.0
CELL_W = 44.0
BEZ = 10


def bez(p0, p1, p2, p3, n=BEZ):
    out = []
    for i in range(1, n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def d_paths(d):
    """把 PyMuPDF 一个 drawing 转成折线列表（页面点坐标）"""
    paths, cur = [], []
    for it in d['items']:
        k = it[0]
        if k == 'l':
            p0, p1 = it[1], it[2]
            if not cur or (abs(cur[-1][0] - p0.x) > 1e-3 or abs(cur[-1][1] - p0.y) > 1e-3):
                if cur:
                    paths.append(cur)
                cur = [(p0.x, p0.y)]
            cur.append((p1.x, p1.y))
        elif k == 'c':
            p0, p1, p2, p3 = it[1], it[2], it[3], it[4]
            if not cur or (abs(cur[-1][0] - p0.x) > 1e-3 or abs(cur[-1][1] - p0.y) > 1e-3):
                if cur:
                    paths.append(cur)
                cur = [(p0.x, p0.y)]
            cur += bez((p0.x, p0.y), (p1.x, p1.y), (p2.x, p2.y), (p3.x, p3.y))
        elif k == 're':
            r = it[1]
            if cur:
                paths.append(cur)
                cur = []
            paths.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)])
        elif k == 'qu':
            q = it[1]
            if cur:
                paths.append(cur)
                cur = []
            paths.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)])
    if cur:
        paths.append(cur)
    return paths


def main(pdfdir, specdir, outdir, report=False):
    pdfdir, specdir, outdir = Path(pdfdir), Path(specdir), Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    sizes = json.loads((Path(__file__).resolve().parent.parent / 'assets' / 'plant_symbols.json').read_text(encoding='utf-8'))
    cat = json.loads((Path(__file__).resolve().parent.parent / 'assets' / 'symbol_catalog.json').read_text(encoding='utf-8'))
    res, dots = {}, []
    for pj in sorted(specdir.glob('SYM-ATLAS-*.json')):
        if pj.name.endswith(('.props.json', '.ids.json')):
            continue
        spec = json.loads(pj.read_text(encoding='utf-8'))
        doc = fitz.open(pdfdir / (pj.stem + '.pdf'))
        page = doc[0]
        H = page.rect.height * PT2MM
        draws = page.get_drawings()
        allp = []
        for d in draws:
            for pts in d_paths(d):
                mm = [(x * PT2MM, H - y * PT2MM) for x, y in pts]
                allp.append((mm, d.get('fill') is not None, d.get('closePath', False)))
        for it in spec['items']:
            if it['k'] != 'sym':
                continue
            st = it['style']
            bb = (cat.get(st) or sizes.get(st) or {}).get('bbox')
            if not bb:
                continue
            k = it.get('scale', style_scale(st)) / style_scale(st)      # spec 里的 scale 是绝对比例，除以样式默认比例得到图集缩放
            ox, oy = it['at']
            cx, cy = ox + (bb[0] + bb[2]) / 2 * k, oy + (bb[1] + bb[3]) / 2 * k
            # 符号区：格宽 ±21，高从格顶往下约 25 mm（标注在其下方）
            xlo, xhi, ylo, yhi = cx - 22.0, cx + 22.0, cy - 14.4, cy + 14.4
            sel = []
            for mm, fill, closed in allp:
                if all(xlo <= x <= xhi and ylo <= y <= yhi for x, y in mm):   # 整条路径都在符号区内（排除下方的标注文字）
                    sel.append(((tuple(((x - ox) / k, (y - oy) / k) for x, y in mm)), fill, closed))
            xs = [p[0] for s in sel for p in s[0]]
            ys = [p[1] for s in sel for p in s[0]]
            if not xs:
                dots.append(st)
                res[st] = {'dot': True, 'paths': [], 'bbox': [0, 0, 0, 0]}
                continue
            w, h = (max(xs) - min(xs)) * k, (max(ys) - min(ys)) * k
            is_dot = (w < 1.5 and h < 1.5) or len(sel) < 1
            if is_dot:
                dots.append(st)
            res[st] = {
                'dot': bool(is_dot),
                'bbox': [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)],
                'paths': [] if is_dot else [{'pts': [[round(x, 3), round(y, 3)] for x, y in s[0]], 'closed': bool(s[2]), 'fill': bool(s[1])} for s in sel],
                'n': len(sel),
            }
    (outdir / 'plant_symbols_geom.json').write_text(json.dumps(res, ensure_ascii=False), encoding='utf-8')
    print('提取', len(res), '个符号，其中几何缺失（点）', len(dots), '个')
    if report:
        print('几何缺失：', ' | '.join(dots))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(*a[:3], report='--report' in sys.argv)
