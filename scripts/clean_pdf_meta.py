"""清理 PDF 元数据（交付前）：标题改为图号+图名，作者/主题/关键字/创建者/生成器清空，删除 XMP。
用法: python clean_pdf_meta.py <pid_model.json> <PDF 目录> [输出目录]   （不给输出目录则原地改写）
"""
import json
import sys
from pathlib import Path

import fitz


def clean(doc, title):
    doc.set_metadata({'title': title, 'author': '', 'subject': '', 'keywords': '', 'creator': '', 'producer': ''})
    try:
        doc.del_xml_metadata()
    except Exception:
        pass


def main(model, src, out=None):
    M = json.loads(Path(model).read_text(encoding='utf-8'))
    src = Path(src)
    out = Path(out) if out else src
    out.mkdir(parents=True, exist_ok=True)
    for sh in M['sheets']:
        f = src / f"{sh['no']}.pdf"
        if not f.exists():
            print('缺少', f.name)
            continue
        d = fitz.open(f)
        clean(d, f"{sh['no']}  {sh['title']}")
        tmp = out / (f.stem + '.tmp.pdf')
        d.save(tmp, garbage=3, deflate=True)
        d.close()
        tmp.replace(out / f.name)
        print('已清理', f.name)


if __name__ == '__main__':
    main(*sys.argv[1:4])
