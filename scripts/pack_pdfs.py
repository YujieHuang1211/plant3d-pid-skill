"""按 pid_model.json 的图纸顺序把各张 PDF 合并为一份图集，并核对张数、图幅。
用法: python pack_pdfs.py <pid_model.json> <PDF 目录> <输出 PDF> [制图配置名，缺省 legacy-2026-10]
"""
import json
import sys
from pathlib import Path

import fitz



def main(model, src, out, profile=None):
    import drawprofile
    S = drawprofile.sheet(drawprofile.load(profile))
    want = (round(S['width']), round(S['height']))
    M = json.loads(Path(model).read_text(encoding='utf-8'))
    src = Path(src)
    book = fitz.open()
    toc = []
    for sh in M['sheets']:
        f = src / f"{sh['no']}.pdf"
        if not f.exists():
            raise SystemExit(f'缺少 {f.name}')
        d = fitz.open(f)
        if d.page_count != 1:
            raise SystemExit(f'{f.name} 有 {d.page_count} 页，每张图的 PDF 应恰为 1 页')
        r = d[0].rect
        if (round(r.width / 72 * 25.4), round(r.height / 72 * 25.4)) != want:
            raise SystemExit(f'{f.name} 图幅不是 {S["name"]}（{want[0]}×{want[1]}）')
        toc.append([1, f"{sh['no']}  {sh['title']}", book.page_count + 1])
        book.insert_pdf(d)
    if book.page_count != len(M['sheets']):
        raise SystemExit(f'图集 {book.page_count} 页，模型有 {len(M["sheets"])} 张图')
    book.set_toc(toc)
    book.set_metadata({'title': f"{M['meta']['project']} P&ID 图集", 'author': '', 'subject': '', 'creator': '', 'producer': ''})
    book.save(out, garbage=3, deflate=True)
    print('合并', book.page_count, '张 →', out)


if __name__ == '__main__':
    main(*sys.argv[1:5])
