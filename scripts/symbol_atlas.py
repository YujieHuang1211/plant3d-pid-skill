"""符号库工具：测量 Plant 库全部符号的外框、生成图集页（看得见每个符号长什么样）、按关键词查符号。
用法:
  python symbol_atlas.py measure-spec <输出目录>
      写 SYM-MEASURE.json：全部符号按网格插入（间距大、不重叠），供一次 AutoCAD 会话量外框
  python symbol_atlas.py parse <info.log> <输出 plant_symbols.json>
      读 `info` 日志里的块参照外框，得到每个样式相对插入点的外框（mm）
  python symbol_atlas.py atlas-specs <plant_symbols.json> <输出目录>
      按类别写图集页 SYM-ATLAS-01…（每格：符号、中文名、英文样式名、实际大小），出 PDF 后看图选符号
  python symbol_atlas.py find <关键词…>
      按中/英文关键词查符号：样式名、中文名、类别、外框尺寸、所在图集页
符号来源：Plant 自带符号库（assets/plant_asset_styles.json，178 个）+ 技能自带和项目自定义的 QMZ 符号（assets/symbol_catalog.json）。
"""
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / 'assets'
STYLES = ASSETS / 'plant_asset_styles.json'
NAMES = ASSETS / 'symbol_names_zh.json'
SIZES = ASSETS / 'plant_symbols.json'
CELL_W, CELL_H = 44.0, 36.0          # 图集每格（mm）
COLS, ROWS = 8, 5                    # 每页 8×5 = 40 格；底边 y=96，在标题栏上方
X0, Y0 = 30.0, 276.0                 # 左上角


LAYERS = [{'name': '符号', 'color': 7, 'lw': 35}, {'name': '位号', 'color': 3, 'lw': 25}, {'name': '注释', 'color': 7, 'lw': 18}]


def style_scale(st):
    """样式默认比例：Plant 库样式取 plant_style_scales.json（stylesof 导出），QMZ 自定义样式为 1"""
    p = ASSETS / 'plant_style_scales.json'
    d = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    return float(d.get(st, {}).get('scale', 1.0))


def load_styles():
    return json.loads(STYLES.read_text(encoding='utf-8'))


def load_names():
    return json.loads(NAMES.read_text(encoding='utf-8')) if NAMES.exists() else {}


def measure_spec(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for i, st in enumerate(load_styles()):
        items.append({'k': 'sym', 'style': st, 'at': [200.0 + (i % 12) * 150, 200.0 - (i // 12) * 120], 'rot': 0, 'layer': '符号'})
    (out / 'SYM-MEASURE.json').write_text(json.dumps({'clear': False, 'items': items}, ensure_ascii=False), encoding='utf-8')
    print('写出', out / 'SYM-MEASURE.json', len(items), '个符号')


BLK = re.compile(r'BlockReference h=\w+ layer=(\S+) \[(-?[\d.]+),(-?[\d.]+)\]-\[(-?[\d.]+),(-?[\d.]+)\] block=(.+?)(?= row=| tag=|$)')


def parse(info_log, out):
    styles = load_styles()
    refs = []
    for ln in Path(info_log).read_text(encoding='utf-8', errors='replace').splitlines():
        m = BLK.search(ln)
        if m and m.group(1) == '符号':
            refs.append(tuple(map(float, m.group(2, 3, 4, 5))) + (m.group(6),))
    if len(refs) < len(styles):
        print(f'警告：只读到 {len(refs)} 个块参照，样式 {len(styles)} 个（个别符号可能没画出来）')
    res = {}
    for i, st in enumerate(styles):
        if i >= len(refs):
            break
        x0, y0, x1, y1, blk = refs[i]
        px, py = 200.0 + (i % 12) * 150, 200.0 - (i // 12) * 120
        res[st] = {'bbox': [round(x0 - px, 2), round(y0 - py, 2), round(x1 - px, 2), round(y1 - py, 2)], 'block': blk}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('写出', out, len(res), '个样式')


def category(st, names):
    return names.get(st, {}).get('cat', '其他')


def atlas_specs(sizes_json, out):
    sizes = json.loads(Path(sizes_json).read_text(encoding='utf-8'))
    cat = json.loads((ASSETS / 'symbol_catalog.json').read_text(encoding='utf-8'))
    names = load_names()
    entries = []
    for st in load_styles():
        if st in sizes:
            entries.append((st, sizes[st]['bbox']))
    for st, v in cat.items():
        if st.startswith('QMZ') and st not in {e[0] for e in entries}:
            entries.append((st, v['bbox']))
    order = ['设备', '泵与压缩机', '换热器', '容器与储罐', '手动阀', '调节阀与执行机构', '减压与安全', '过滤', '流量与测量元件', '仪表与逻辑', '管嘴与法兰', '管件与连接', '其他']
    entries.sort(key=lambda e: (order.index(category(e[0], names)) if category(e[0], names) in order else 99, e[0]))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    per = COLS * ROWS
    pages = [entries[i:i + per] for i in range(0, len(entries), per)]
    index = {}
    for pn, page in enumerate(pages, 1):
        items = []
        no = f'SYM-ATLAS-{pn:02d}'
        items.append({'k': 'text', 'at': [30, 290], 'text': f'符号库图集 第 {pn} / {len(pages)} 页（符号按实际大小的比例缩放显示，格内标注实际宽×高 mm）', 'h': 3.5, 'just': 'ML', 'layer': '注释'})
        for i, (st, bb) in enumerate(page):
            col, row = i % COLS, i // COLS
            cx = X0 + col * CELL_W + CELL_W / 2
            cy = Y0 - row * CELL_H - 14
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            # 缩放：最大边不超过 26 mm；太小的符号放大到至少 8 mm
            k = 1.0
            big = max(w, h, 0.1)
            if big > 26:
                k = 26 / big
            elif big < 8:
                k = min(8 / big, 4.0)
            ox = cx - (bb[0] + bb[2]) / 2 * k
            oy = cy - (bb[1] + bb[3]) / 2 * k
            it = {'k': 'sym', 'style': st, 'at': [round(ox, 2), round(oy, 2)], 'rot': 0, 'layer': '符号'}
            if abs(k - 1) > 1e-6:
                it['scale'] = round(k * style_scale(st), 4)     # sym 的 scale 是绝对比例（替代样式默认比例），所以要乘样式自带比例
            items.append(it)
            zh = names.get(st, {}).get('zh', '')
            items.append({'k': 'rect', 'pts': [[X0 + col * CELL_W, Y0 - row * CELL_H], [X0 + (col + 1) * CELL_W, Y0 - (row + 1) * CELL_H]], 'layer': '注释'}) if False else None
            items.append({'k': 'text', 'at': [round(cx, 2), round(Y0 - row * CELL_H - 29.5, 2)], 'text': zh or st.replace(' Style', ''), 'h': 2.8, 'just': 'MC', 'layer': '位号'})
            items.append({'k': 'text', 'at': [round(cx, 2), round(Y0 - row * CELL_H - 33.2, 2)], 'text': f'{w:.0f}×{h:.0f} mm  {st.replace(" Style", "")}'[:34], 'h': 1.8, 'just': 'MC', 'layer': '注释'})
            index[st] = no
        items = [x for x in items if x]
        (out / f'{no}.json').write_text(json.dumps({'clear': False, 'layers': LAYERS, 'items': items}, ensure_ascii=False), encoding='utf-8')
        (out / f'{no}.props.json').write_text(json.dumps({'PnID': no, 'Title': f'符号库图集 {pn}', 'Description': '符号库图集', 'Area': '—', 'Author': '—', 'Revision': 'A', 'Stage': '—', 'Scale': 'NTS',
                                                         'SheetNo': str(pn), 'SheetTotal': str(len(pages)), 'Checker': '—', 'Reviewer': '—', 'Approver': '—', 'IssueDate': '—', 'RevNote': '—'}, ensure_ascii=False), encoding='utf-8')
    (ASSETS / 'symbol_atlas_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
    print('写出', len(pages), '页，', len(index), '个符号；索引 assets/symbol_atlas_index.json')


def find(words):
    """按中/英文关键词查符号；--png <文件> 把命中的符号画成一张图"""
    png_out = None
    if '--png' in words:
        k = words.index('--png')
        png_out = words[k + 1]
        words = words[:k] + words[k + 2:]
    sys.path.insert(0, str(HERE))
    import symbol_geom
    g = symbol_geom.load()
    names = load_names()
    idx = json.loads((ASSETS / 'symbol_atlas_index.json').read_text(encoding='utf-8')) if (ASSETS / 'symbol_atlas_index.json').exists() else {}
    cat = json.loads((ASSETS / 'symbol_catalog.json').read_text(encoding='utf-8'))
    hits = []
    for st in sorted(set(list(g) + list(names) + list(cat))):
        n = names.get(st, {})
        blob = ' '.join([st, n.get('zh', ''), n.get('cat', ''), n.get('use', '')]).lower()
        if all(w.lower() in blob for w in words):
            hits.append(st)
    for st in hits:
        n = names.get(st, {})
        bb = (g.get(st) or cat.get(st) or {}).get('bbox')
        size = f'{bb[2] - bb[0]:.0f}×{bb[3] - bb[1]:.0f} mm' if bb else '未知'
        kind = '手工新增（折线几何，不依赖项目样式）' if g.get(st, {}).get('native') else ('Plant 库样式（有几何库，可 --geom-all 画成折线）' if st in g else '项目/QMZ 自定义样式')
        print(st)
        print(f"   {n.get('zh', '（无中文名）')} | {n.get('cat', '其他')} | {size} | {kind} | 图集 {idx.get(st, '—')}")
        print(f"   用途：{n.get('use', '')}")
    if not hits:
        print('库里没有。方法：上网搜 GB/T 6567、ISO 10628、ISA 5.1 的标准图形，用 symbol_geom.py 的 DEFS 新增（见 references/symbol_library.md）。')
    elif png_out:
        symbol_geom.png(png_out, [h for h in hits if h in g][:24])
    return hits


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == 'measure-spec':
        measure_spec(a[1])
    elif a[0] == 'parse':
        parse(a[1], a[2])
    elif a[0] == 'atlas-specs':
        atlas_specs(a[1], a[2])
    elif a[0] == 'find':
        find(a[1:])
    else:
        print(__doc__)
