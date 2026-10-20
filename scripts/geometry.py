"""符号几何的唯一实现：平移、旋转、缩放、连接点、外框。plain_convert、lint_specs、pidlib.attach、autolabel、preview_spec 都调用这里，
预览、检查和 CAD 出图因此得到同一组连接点。

spec 里 scale 的含义（沿用转换器现行规则，不得改变，否则已有版面模块会变形）：
  · 手工新增（native）符号：scale 是倍数
  · Plant 库符号：scale 是绝对比例，倍数 = scale ÷ plant_style_scales.json 里该样式的默认比例
样式不在 plant_style_scales.json 时倍数无法确定：factor() 返回 known=False（lint 报错），按 1 计。
"""
import json
import math
from pathlib import Path

import symbol_geom

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
try:
    STYLE_SCALES = json.loads((ASSETS / 'plant_style_scales.json').read_text(encoding='utf-8'))
except Exception:
    STYLE_SCALES = {}
GEOM = symbol_geom.load()


def rot(dx, dy, deg):
    a = math.radians(deg)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def factor(style, scale=None):
    """(倍数, 是否已知)。scale 为 None 表示 spec 没写比例，倍数 1"""
    if scale is None:
        return 1.0, True
    if (GEOM.get(style) or {}).get('native'):
        return float(scale), True
    d = (STYLE_SCALES.get(style) or {}).get('scale')
    if not d:
        return 1.0, False
    return float(scale) / float(d), True


def item_factor(it):
    st = it.get('style') or it.get('body')
    return factor(st, it.get('scale'))[0]


def ports(cat, style, at, ang=0, scale=None):
    """连接点（世界坐标）。目录无此样式返回 []"""
    c = cat.get(style)
    if not c:
        return []
    f = factor(style, scale)[0]
    return [(at[0] + rot(dx * f, dy * f, ang)[0], at[1] + rot(dx * f, dy * f, ang)[1]) for dx, dy in c['att']]


def box(cat, style, at, ang=0, scale=None):
    """符号外框 (x0, y0, x1, y1)（世界坐标，含旋转和比例）；目录无此样式返回 None"""
    c = cat.get(style)
    if not c:
        return None
    f = factor(style, scale)[0]
    x0, y0, x1, y1 = (v * f for v in c['bbox'])
    cs = [rot(dx, dy, ang) for dx, dy in ((x0, y0), (x1, y1), (x0, y1), (x1, y0))]
    return (at[0] + min(p[0] for p in cs), at[1] + min(p[1] for p in cs), at[0] + max(p[0] for p in cs), at[1] + max(p[1] for p in cs))


def placed(cat, style, at, ang=0, scale=None):
    """(外框, 连接点)；目录无此样式返回 None"""
    b = box(cat, style, at, ang, scale)
    return None if b is None else (b, ports(cat, style, at, ang, scale))


def inline_ports(cat, it):
    """内联符号两端连接点（绝对坐标）；目录无连接点时取外框左右中点"""
    st = it.get('style') or it.get('body')
    c = cat.get(st) or {}
    att = c.get('att') or []
    if len(att) >= 2:
        pa, pb = att[0], att[-1]
    else:
        bb = c.get('bbox') or [-4, -2, 4, 2]
        pa, pb = [bb[0], 0], [bb[2], 0]
    f = item_factor(it)
    x, y = it['at']
    out = []
    for p in (pa, pb):
        dx, dy = rot(p[0] * f, p[1] * f, it.get('rot', 0))
        out.append([x + dx, y + dy])
    return out


def item_box(cat, it):
    """spec 条目（asset/cv/sym）的外框；目录无样式时按默认 ±4×±2"""
    st = it.get('style') or it.get('body')
    if (cat.get(st) or {}).get('bbox'):
        return box(cat, st, it['at'], it.get('rot', 0), it.get('scale'))
    bb = [-4, -2, 4, 2]
    f = item_factor(it)
    cs = [rot(dx * f, dy * f, it.get('rot', 0)) for dx, dy in ((bb[0], bb[1]), (bb[2], bb[3]), (bb[0], bb[3]), (bb[2], bb[1]))]
    x, y = it['at']
    return (x + min(c[0] for c in cs), y + min(c[1] for c in cs), x + max(c[0] for c in cs), y + max(c[1] for c in cs))
