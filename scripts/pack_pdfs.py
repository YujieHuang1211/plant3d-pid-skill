"""按 pid_model.json 的图纸顺序把各张 PDF 合并为一份图集，并核对张数、图幅。
用法: python pack_pdfs.py <pid_model.json> <PDF 目录> <输出 PDF>
"""
import json
import sys
from pathlib import Path

import fitz



def main(model, src, out):
    M = json.loads(Path(model).read_text(encoding='utf-8'))
    src = Path(src)
    book = fitz.open()
    toc = []
    for sh in M['sheets']:
        f = src / f"{sh['no']}.pdf"
        if not f.exists():
            raise SystemExit(f'缺少 {f.name}')
        d = fitz.open(f)
        r = d[0].rect
        if (round(r.width / 72 * 25.4), round(r.height / 72 * 25.4)) != (420, 297):
            raise SystemExit(f'{f.name} 图幅不是 A3 横向')
        toc.append([1, f"{sh['no']}  {sh['title']}", book.page_count + 1])
        book.insert_pdf(d)
    book.set_toc(toc)
    book.set_metadata({'title': f"{M['meta']['project']} P&ID 图集", 'author': '', 'subject': '', 'creator': '', 'producer': ''})
    book.save(out, garbage=3, deflate=True)
    print('合并', book.page_count, '张 →', out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
