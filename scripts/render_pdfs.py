"""把出图 PDF 渲染为 PNG 供逐张目检，并核对图幅（按制图配置的图幅，缺省 A3 横向 420×297 mm）。
用法: python render_pdfs.py <PDF 目录> <PNG 输出目录> [制图配置名]
"""
import json
import sys
from pathlib import Path

import fitz

MM = 72 / 25.4


def main(src, out, profile=None):
    src, out = Path(src), Path(out)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import drawprofile
    S = drawprofile.sheet(drawprofile.load(profile))
    want = (round(S['width']), round(S['height']))
    out.mkdir(parents=True, exist_ok=True)
    rep = []
    for pdf in sorted(src.glob('*.pdf')):
        d = fitz.open(pdf)
        for i, p in enumerate(d):
            w, h = round(p.rect.width / MM), round(p.rect.height / MM)
            png = out / f'{pdf.stem}-p{i + 1}.png'
            p.get_pixmap(matrix=fitz.Matrix(1.7, 1.7)).save(png)
            rep.append({'pdf': pdf.name, 'page': i + 1, 'size_mm': [w, h], 'a3_landscape': (w, h) == want, 'sheet': S['name'], 'png': png.name})
    (out / '渲染清单.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in rep:
        print(r['pdf'], r['page'], r['size_mm'], 'OK' if r['a3_landscape'] else '图幅不符')


if __name__ == '__main__':
    main(*sys.argv[1:4])
