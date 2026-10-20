"""测试公用：把 scripts/ 放进 sys.path，造 A3 横向 PDF、写 JSON 的小工具。全部在临时目录，不碰 CAD。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
GOLDEN = Path(__file__).resolve().parent / 'golden'
A3_PT = (420 * 72 / 25.4, 297 * 72 / 25.4)


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def make_pdf(path, pages=1, size=A3_PT):
    import fitz
    d = fitz.open()
    for _ in range(pages):
        d.new_page(width=size[0], height=size[1])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    d.save(path)
    d.close()
