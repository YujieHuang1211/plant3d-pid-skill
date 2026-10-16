"""非智能对象的符号几何库：每个符号 = 若干折线（相对插入点，mm，比例 1），与 Plant 样式无关。
来源有两类：
  assets/symbols_geom.json   从 Plant 自带符号库（PIP/ISA）的图集 PDF 提取（extract_symbol_geom.py），194 个
  assets/native_symbols.json 手工定义的新增符号（本文件末尾的 DEFS 生成），Plant 库里没有的设备/元件
用法（模块）:
  from symbol_geom import load, polys, bbox
  load()                                  # {样式名: {"paths": [...], "bbox": [...], "native": bool}}
  polys('Gas Cylinder Style', at, rot, scale)   # → [{'pts': [[x,y],…], 'closed': bool, 'fill': bool}]（图面坐标）
命令行:
  python symbol_geom.py build-native      重新生成 assets/native_symbols.json（改 DEFS 后运行）
  python symbol_geom.py png <输出.png> <样式名…>   画出指定符号，目测检查
  python symbol_geom.py sheet <输出目录>        按类别画整套图集 PNG（不需要 AutoCAD）
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / 'assets'
_CACHE = {}


def load():
    if not _CACHE:
        g = json.loads((ASSETS / 'symbols_geom.json').read_text(encoding='utf-8')) if (ASSETS / 'symbols_geom.json').exists() else {}
        n = json.loads((ASSETS / 'native_symbols.json').read_text(encoding='utf-8')) if (ASSETS / 'native_symbols.json').exists() else {}
        for k, v in g.items():
            v['native'] = False
            _CACHE[k] = v
        for k, v in n.items():
            v['native'] = True
            _CACHE[k] = v
    return _CACHE


def bbox(style):
    return load()[style]['bbox']


def eff_scale(style, scale=None):
    """spec 里 sym 的 scale 对 Plant 库样式是绝对比例（替代样式默认比例），对手工新增符号是倍数；换算成几何库的倍数"""
    if scale is None:
        return 1.0
    if load()[style].get('native'):
        return float(scale)
    sc = json.loads((ASSETS / 'plant_style_scales.json').read_text(encoding='utf-8')).get(style, {}).get('scale', 1.0) if (ASSETS / 'plant_style_scales.json').exists() else 1.0
    return float(scale) / float(sc or 1.0)


def polys(style, at, rot=0.0, scale=1.0, mirror=False):
    """符号折线变换到图面坐标：先缩放（可镜像），再旋转 rot 度，再平移到 at"""
    s = load()[style]
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for p in s['paths']:
        pts = []
        for x, y in p['pts']:
            x, y = x * scale, y * scale
            if mirror:
                x = -x
            pts.append([round(at[0] + x * ca - y * sa, 3), round(at[1] + x * sa + y * ca, 3)])
        out.append({'pts': pts, 'closed': p.get('closed', False), 'fill': p.get('fill', False)})
    return out


# ------------------------------------------------------------------ 手工定义的新增符号（Plant 库没有）
def _circle(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def _arc(cx, cy, r, a0, a1, n=16):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _zig(x0, x1, y0, n, dy):
    pts, y, left = [], y0, True
    for _ in range(n):
        pts.append((x0 if left else x1, y))
        y += dy
        left = not left
    pts.append((x0 if left else x1, y))
    return pts


def P(pts, closed=False, fill=False):
    return {'pts': [[round(x, 3), round(y, 3)] for x, y in pts], 'closed': closed, 'fill': fill}


# 约定：插入点在符号几何中心；管道接口见 ports（相对插入点）。尺寸为 A3 打印毫米，一般 P&ID 比例。
DEFS = {
    'Gas Cylinder Style': dict(zh='气瓶', cat='设备', use='高压气瓶（CO₂、H₂、N₂、Ar 等），带瓶阀；出口在顶部', ports={'out': (0, 14)}, paths=[
        P(_arc(0, 8, 4, 0, 180) + [(-4, -10), (4, -10)] + [(4, 8)], False), P([(-4, 8), (-4, -10), (4, -10), (4, 8)]), P(_arc(0, 8, 4, 0, 180)),
        P([(-1.2, 12), (-1.2, 14), (1.2, 14), (1.2, 12)]), P([(-3, 14.5), (3, 14.5)])]),
    'Electric Heater Style': dict(zh='电加热器', cat='换热器', use='管道/气体电加热器、预热器', ports={'in': (-9, 0), 'out': (9, 0)}, paths=[
        P(_rect(-7, -4, 7, 4), True), P(_zig(-5, 5, -2.5, 5, 1.0)), P([(-9, 0), (-7, 0)]), P([(7, 0), (9, 0)])]),
    'Chiller Style': dict(zh='冷水机/冷冻机组', cat='换热器', use='循环冷却水机组、低温恒温槽', ports={'in': (-12, 3), 'out': (12, 3)}, paths=[
        P(_rect(-10, -7, 10, 7), True), P(_circle(0, 0, 3.5)), P([(-1.8, -1.8), (1.8, 1.8)]), P([(-1.8, 1.8), (1.8, -1.8)]),
        P([(-12, 3), (-10, 3)]), P([(10, 3), (12, 3)]), P([(-7, 7), (-7, 9)]), P([(7, 7), (7, 9)])]),
    'Cold Trap Style': dict(zh='冷阱', cat='容器与储罐', use='冷凝收集（U 形管浸入冷浴）', ports={'in': (-3, 12), 'out': (3, 12)}, paths=[
        P([(-3, 12), (-3, -5)] + _arc(0, -5, 3, 180, 360) + [(3, 12)]), P(_rect(-7, -9, 7, 3), True), P([(-7, -1), (7, -1)])]),
    'Desiccant Dryer Style': dict(zh='干燥器/干燥塔', cat='过滤', use='气体干燥（硅胶、分子筛）', ports={'in': (0, 12), 'out': (0, -12)}, paths=[
        P([(-4, 8)] + _arc(0, 8, 4, 180, 0) + [(4, -8)] + _arc(0, -8, 4, 360, 180) + [(-4, 8)]), P([(-4, 3), (4, 3)]), P([(-4, -3), (4, -3)]),
        P([(0, 12), (0, 12)]), P([(0, 12), (0, 12)])]),
    'Coriolis Meter Style': dict(zh='科氏质量流量计', cat='流量与测量元件', use='液体/气体质量流量计', ports={'in': (-9, 0), 'out': (9, 0)}, paths=[
        P(_rect(-6, -4, 6, 4), True), P([(-9, 0), (-6, 0)]), P([(6, 0), (9, 0)]), P(_arc(-1.8, 0, 2.2, 90, 270)), P(_arc(1.8, 0, 2.2, -90, 90))]),
    'Pressure Gauge Style': dict(zh='就地压力表', cat='仪表与逻辑', use='现场就地压力表（不上传信号）', ports={'in': (0, -5)}, paths=[
        P(_circle(0, 0, 4)), P([(0, -4), (0, -5)]), P([(0, 0), (2.5, 2.5)]), P(_arc(0, 0, 2.8, 20, 160))]),
    'Vacuum Pump Dry Style': dict(zh='干式真空泵', cat='泵与压缩机', use='无油干式真空泵（实验室常用）', ports={'in': (-9, 0), 'out': (9, 6)}, paths=[
        P(_circle(0, 0, 7)), P([(-9, 0), (-7, 0)]), P([(7, 6), (9, 6)]), P([(-7, 0), (0, 5), (7, 0)])]),
    'Syringe Pump Style': dict(zh='注射泵', cat='泵与压缩机', use='微量精密进液', ports={'out': (10, 0)}, paths=[
        P(_rect(-10, -2.5, 6, 2.5), True), P([(6, 0), (10, 0)]), P([(-10, 0), (-13, 0)]), P([(-13, -3), (-13, 3)]), P([(-7, -2.5), (-7, 2.5)])]),
    'Heat Tracing Style': dict(zh='伴热带', cat='设备', use='管道电伴热', ports={'in': (-8, 0), 'out': (8, 0)}, paths=[
        P([(-8, 0), (8, 0)]), P(_arc(-4, 0, 2, 180, 0)), P(_arc(0, 0, 2, 180, 360)), P(_arc(4, 0, 2, 180, 0))]),
    'Mass Spectrometer Style': dict(zh='质谱/色谱分析仪', cat='仪表与逻辑', use='在线分析仪（GC、MS、红外等），位号 AIT/AE', ports={'in': (-8, 0)}, paths=[
        P(_rect(-6, -5, 6, 5), True), P([(-8, 0), (-6, 0)]), P([(-4, -2.5), (-2, 2.5), (0, -2.5), (2, 2.5), (4, -2.5)])]),
    'Horizontal Drum Style': dict(zh='卧式容器/卧式罐', cat='容器与储罐', use='卧式缓冲罐、分液罐', ports={'in_l': (-13, 0), 'out_r': (13, 0), 'top': (0, 7), 'bottom': (0, -7)}, paths=[
        P([(-8, 5), (8, 5)] + _arc(8, 0, 5, 90, -90) + [(-8, -5)] + _arc(-8, 0, 5, 270, 90)), P([(0, 5), (0, 7)]), P([(0, -5), (0, -7)])]),
    'Jacketed Reactor Style': dict(zh='夹套反应釜（带搅拌）', cat='容器与储罐', use='带夹套和搅拌的釜式反应器', ports={'top': (0, 20), 'bottom': (0, -20), 'jacket_in': (10, -8), 'jacket_out': (10, 4)}, paths=[
        P([(-8, 10), (-8, -10)] + _arc(0, -10, 8, 180, 360) + [(8, 10)]), P(_arc(0, 10, 8, 0, 180)),
        P([(-8, 5), (-10, 5), (-10, -10)] + _arc(0, -10, 10, 180, 360) + [(10, 5), (8, 5)]),
        P([(0, 18), (0, -6)]), P([(-4, -6), (4, -6)]), P(_rect(-3, 18, 3, 22)), P([(0, 18), (0, 18)]), P([(0, -18), (0, -20)])]),
    'Gas Bag Style': dict(zh='气袋/采样袋', cat='容器与储罐', use='气体采样、收集', ports={'in': (0, 10)}, paths=[
        P([(-6, -8), (-6, 6), (-4, 8), (4, 8), (6, 6), (6, -8), (-6, -8)]), P([(-1.5, 8), (-1.5, 10), (1.5, 10), (1.5, 8)]), P([(-6, -4), (6, -4)])]),
    'Gas Washing Bottle Style': dict(zh='洗气瓶/鼓泡瓶', cat='容器与储罐', use='气体洗涤、鼓泡、液封', ports={'in': (-2, 14), 'out': (3, 14)}, paths=[
        P([(-6, -9), (-6, 4)] + _arc(0, 4, 6, 180, 0)[1:] + [(6, -9), (-6, -9)]), P([(-2, 14), (-2, -6)]), P([(3, 14), (3, 6)]), P([(-6, -2), (6, -2)])]),
    'Quick Connector Style': dict(zh='快插接头', cat='管件与连接', use='可快速拆装的气路接头，临时连接处', ports={'l': (-6, 0), 'r': (6, 0)}, paths=[
        P([(-6, 0), (-3, 0)]), P([(3, 0), (6, 0)]), P(_rect(-3, -2, -0.5, 2), True), P(_rect(0.5, -2, 3, 2), True)]),
    'Power Supply Style': dict(zh='电源/电源柜', cat='设备', use='热等离子体电源、直流电源、加热电源', ports={'out': (10, 0)}, paths=[
        P(_rect(-9, -6, 9, 6), True), P(_arc(-4, 1.2, 2, 0, 180) + _arc(0, 1.2, 2, 180, 360)[1:]), P([(2.5, -2.5), (8, -2.5)]), P([(2.5, -4), (8, -4)]), P([(9, 0), (10, 0)])]),
    'Orifice Plate Union Style': dict(zh='限流孔板/节流件', cat='流量与测量元件', use='限流', ports={'in': (-5, 0), 'out': (5, 0)}, paths=[
        P([(-5, 0), (-1, 0)]), P([(1, 0), (5, 0)]), P([(-1, -3), (-1, 3)]), P([(1, -3), (1, 3)])]),
}


def _bbox(paths):
    xs = [p[0] for pa in paths for p in pa['pts']]
    ys = [p[1] for pa in paths for p in pa['pts']]
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]


def build_native():
    out = {}
    for st, d in DEFS.items():
        out[st] = {'paths': d['paths'], 'bbox': _bbox(d['paths']), 'ports': {k: list(v) for k, v in d.get('ports', {}).items()}}
    cat_p = ASSETS / 'symbol_catalog.json'
    cat = json.loads(cat_p.read_text(encoding='utf-8'))
    for st, d in DEFS.items():      # 同步到符号目录，lint 和预览才认得这些样式
        att = [list(v) for v in d.get('ports', {}).values()]
        cat[st] = {'bbox': out[st]['bbox'], 'att': att, 'scale': 1.0, 'from_ang': 0, 'native': True}
    cat_p.write_text(json.dumps(dict(sorted(cat.items())), ensure_ascii=False, indent=1), encoding='utf-8')
    (ASSETS / 'native_symbols.json').write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding='utf-8')
    names_p = ASSETS / 'symbol_names_zh.json'
    names = json.loads(names_p.read_text(encoding='utf-8'))
    for st, d in DEFS.items():
        names[st] = {'zh': d['zh'], 'cat': d['cat'], 'use': d['use'], 'native': True}
    names_p.write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding='utf-8')
    print('写出', len(out), '个新增符号 → assets/native_symbols.json，并更新中文名表')


# ------------------------------------------------------------------ 画 PNG（PIL）：目测检查与离线图集
def draw_symbol(d, style, cx, cy, box, label=None, font=None, ppm=8):
    """在 PIL ImageDraw d 上把符号缩放到 box(mm) 以内画在 (cx, cy) 像素处；ppm=每毫米像素"""
    s = load()[style]
    bb = s['bbox']
    w, h = max(bb[2] - bb[0], 0.1), max(bb[3] - bb[1], 0.1)
    k = min(box / max(w, h), 6.0)
    for p in s['paths']:
        pts = [(cx + (x - (bb[0] + bb[2]) / 2) * k * ppm, cy - (y - (bb[1] + bb[3]) / 2) * k * ppm) for x, y in p['pts']]
        if p.get('fill') and p.get('closed') and len(pts) >= 3:
            d.polygon(pts, fill='black')
        elif len(pts) >= 2:
            d.line(pts, fill='black', width=1)
    return k


def sheet(outdir):
    from PIL import Image, ImageDraw, ImageFont
    names = json.loads((ASSETS / 'symbol_names_zh.json').read_text(encoding='utf-8'))
    order = ['设备', '泵与压缩机', '换热器', '容器与储罐', '手动阀', '调节阀与执行机构', '减压与安全', '过滤', '流量与测量元件', '仪表与逻辑', '管嘴与法兰', '管件与连接', '其他']
    g = load()
    items = sorted(g, key=lambda s: (order.index(names.get(s, {}).get('cat', '其他')) if names.get(s, {}).get('cat', '其他') in order else 99, s))
    font = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 14)
    small = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 10)
    cols, rows, cw, ch = 6, 5, 200, 170
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    per = cols * rows
    index = {}
    for pn in range(0, len(items), per):
        page = items[pn:pn + per]
        im = Image.new('RGB', (cols * cw, rows * ch + 30), 'white')
        d = ImageDraw.Draw(im)
        d.text((8, 6), f'符号库图集（几何库，离线绘制）第 {pn // per + 1} 页', fill='black', font=font)
        for i, st in enumerate(page):
            c, r = i % cols, i // cols
            cx, cy = c * cw + cw // 2, 30 + r * ch + 62
            draw_symbol(d, st, cx, cy, 14, ppm=5)
            n = names.get(st, {})
            d.text((cx, 30 + r * ch + 130), n.get('zh', st), fill='black', font=font, anchor='mm')
            d.text((cx, 30 + r * ch + 148), (n.get('cat', '') + ' ' + st.replace(' Style', ''))[:34], fill=(90, 90, 90), font=small, anchor='mm')
        f = out / f'符号库图集_{pn // per + 1:02d}.png'
        im.save(f)
        for st in page:
            index[st] = f.name
        print('写出', f)
    (ASSETS / 'symbol_atlas_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding='utf-8')


def png(out, styles):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 12)
    n = len(styles)
    cols = min(n, 6)
    rows = (n + cols - 1) // cols
    im = Image.new('RGB', (cols * 180, rows * 150), 'white')
    d = ImageDraw.Draw(im)
    for i, st in enumerate(styles):
        cx, cy = (i % cols) * 180 + 90, (i // cols) * 150 + 65
        draw_symbol(d, st, cx, cy, 14, ppm=5)
        d.text((cx, (i // cols) * 150 + 130), st.replace(' Style', ''), fill='black', font=font, anchor='mm')
    im.save(out)
    print('写出', out)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['build-native']:
        build_native()
    elif a[:1] == ['png']:
        png(a[1], a[2:])
    elif a[:1] == ['sheet']:
        sheet(a[1])
    else:
        print(__doc__)
