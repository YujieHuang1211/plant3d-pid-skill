"""spec 离线预览（不需要 AutoCAD，约 1 s/张）：按符号目录外框、管线/信号线、文字、表格画出 A3 版面，标出标题栏禁区。
用于出图前检查版面；预览不是出图结果（符号只画外框与连接点）。
Plant 版 spec 里 Plant 自动标注的位号不画；普通图元 spec（plain_convert 的输出，含 poly / sym / 图层）按图层颜色和线宽画出，
线号、位号、断线、流向箭头位置都在里面，可直接看最终版面。
用法: python preview_spec.py <specs 目录> <输出目录> <图号 ...> [--catalog symbol_catalog.json] [--scale 4]
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lint_specs import DEFAULT_CATALOG, FRAME, TB, placed, table_box, text_box

FONT = 'C:/Windows/Fonts/simsun.ttc'
W, H = 420, 297
STYLE_W = {'Primary Style': 3, 'Secondary Style': 2}
ACI = {1: (230, 0, 0), 2: (200, 160, 0), 3: (0, 150, 0), 4: (0, 160, 170), 5: (0, 0, 220), 6: (200, 0, 200), 7: (0, 0, 0)}


def main(argv):
    args, cat_path, k, cat_extra = [], DEFAULT_CATALOG, 4.0, []
    i = 0
    while i < len(argv):
        if argv[i] == '--catalog':
            if cat_path is DEFAULT_CATALOG:
                cat_path = Path(argv[i + 1])
            else:
                cat_extra.append(argv[i + 1])
            i += 2; continue
        if argv[i] == '--scale':
            k = float(argv[i + 1]); i += 2; continue
        args.append(argv[i]); i += 1
    specdir, outdir, sheets = Path(args[0]), Path(args[1]), args[2:]
    outdir.mkdir(parents=True, exist_ok=True)
    cat = json.loads(cat_path.read_text(encoding='utf-8')) if cat_path.exists() else {}
    for extra in cat_extra:
        cat.update(json.loads(Path(extra).read_text(encoding='utf-8')))

    def P(x, y):
        return (x * k, (H - y) * k)

    for no in sheets:
        spec = json.loads((specdir / f'{no}.json').read_text(encoding='utf-8'))
        items = spec['items']
        layers = {l['name']: l for l in spec.get('layers', [])}
        im = Image.new('RGB', (int(W * k), int(H * k)), 'white')
        d = ImageDraw.Draw(im)
        d.rectangle([P(TB[0], TB[1]), P(FRAME[2], FRAME[1])], fill=(235, 235, 235))
        d.rectangle([P(FRAME[0], FRAME[3]), P(FRAME[2], FRAME[1])], outline='black', width=2)
        fonts = {}

        def font(h):
            s = max(6, int(round(h * k * 0.95)))
            if s not in fonts:
                fonts[s] = ImageFont.truetype(FONT, s)
            return fonts[s]

        for it in items:
            kind = it['k']
            if kind == 'line':
                pts = [P(*p) for p in it['pts']]
                st = it.get('style', '')
                if st in STYLE_W:
                    d.line(pts, fill='black', width=STYLE_W[st])
                else:   # 信号线：虚线
                    col = (200, 0, 0) if 'Electrical' in st else (0, 0, 200)
                    for a, b in zip(pts, pts[1:]):
                        L = math.dist(a, b)
                        n = max(1, int(L / (3 * k)))
                        for j in range(0, n, 2):
                            t0, t1 = j / n, min(1, (j + 1) / n)
                            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                                    (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=col, width=1)
            elif kind in ('asset', 'cv'):
                st = it.get('style') or it.get('body')
                pl = placed(cat, st, it['at'], it.get('rot', 0))
                if pl:
                    (x0, y0, x1, y1), att = pl
                    d.rectangle([P(x0, y1), P(x1, y0)], outline=(0, 120, 0), width=1)
                    for ax, ay in att:
                        cx, cy = P(ax, ay)
                        d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(0, 160, 0))
                else:
                    cx, cy = P(*it['at'])
                    d.line([cx - 8, cy - 8, cx + 8, cy + 8], fill='orange', width=2)
                    d.line([cx - 8, cy + 8, cx + 8, cy - 8], fill='orange', width=2)
                cx, cy = P(*it['at'])
                d.text((cx + 3, cy - 3 * k), it.get('id', ''), fill=(0, 110, 0), font=font(1.8))
            elif kind == 'nozzle':
                cx, cy = P(*it['at'])
                d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline='purple', width=2)
            elif kind == 'text':
                x0, x1, y0, y1 = text_box(it)
                d.rectangle([P(x0, y1), P(x1, y0)], outline=(210, 210, 255))
                h = it.get('h', 3.5)
                txt = str(it['text']).replace('\\S^2;', '2').replace('\\S^4;', '4')
                for code in ('\\L', '\\l', '\\P'):
                    txt = txt.replace(code, '')
                for n, ln in enumerate(txt.split('\n')):
                    d.text(P(x0, y1 - n * h * 1.6), ln, fill='black', font=font(h))
            elif kind == 'table':
                x, y = it['at']
                rows = it['rows']
                yy = y
                for r in rows:
                    nl = max(c.count('\n') + 1 for c in r)
                    hh = nl * it['rowh']
                    xx = x
                    for c, w in zip(r, it['cols']):
                        d.rectangle([P(xx, yy), P(xx + w, yy - hh)], outline='black')
                        for m, ln in enumerate(c.split('\n')):
                            d.text(P(xx + 0.8, yy - 0.8 - m * it['rowh']), ln, fill='black', font=font(it.get('h', 3.5) * 0.8))
                        xx += w
                    yy -= hh
            elif kind == 'poly':
                ly = layers.get(it.get('layer'), {})
                col = ACI.get(ly.get('color', 7), (0, 0, 0))
                wpx = max(1, int(round(ly.get('lw', 25) / 100 * k * 0.8)))
                pts = [P(*p) for p in it['pts']]
                if ly.get('ltype'):
                    for a, b in zip(pts, pts[1:]):
                        L = math.dist(a, b)
                        n = max(1, int(L / (2 * k)))
                        for j in range(0, n, 2):
                            t0, t1 = j / n, min(1, (j + 1) / n)
                            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                                    (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=col, width=wpx)
                else:
                    d.line(pts, fill=col, width=wpx)
            elif kind == 'sym':
                pl = placed(cat, it.get('style', ''), it['at'], it.get('rot', 0))
                if pl:
                    (x0, y0, x1, y1), att = pl
                    d.rectangle([P(x0, y1), P(x1, y0)], outline=(120, 120, 120), width=1)
                else:
                    cx, cy = P(*it['at'])
                    d.rectangle([cx - 3, cy - 3, cx + 3, cy + 3], outline='gray')
        out = outdir / f'{no}.preview.png'
        im.save(out)
        print('预览', out)


if __name__ == '__main__':
    main(sys.argv[1:])
