"""把 Plant 版 spec 转成“普通图元”spec：只含 sym / poly / text / table，不创建任何 Plant 智能对象。
用法: python plain_convert.py <原 specs 目录> <输出目录> [--catalog symbol_catalog.json ...] [--geom-all] [图号 ...]
        --geom-all：Plant 库符号也用几何库画成折线（不依赖项目符号样式；默认只有手工新增的符号这样画）
        （--catalog 可重复，后者覆盖前者；不给图号则转换目录下全部图）

转换规则（引擎 draw 已支持 sym / poly / text / table，不改 C#）：
  asset / cv        → sym（样式块插入；控制阀 = 阀体块 + 执行机构块，同点同转角）
  line              → poly（按样式定线宽/图层/线型）；内联符号处把管线断开；Primary 线末段补一个流向箭头（末端落在管嘴上时退到法兰外）；
                      Software 线中点补小圆
  nozzle            → 接管 + 法兰线（符号层，自设备壁沿 rot 方向）
  connect/tee/opc   → 丢弃（它们只在 Plant 库里有意义）
  原由 Plant 自动生成的文字，改由本脚本按 spec 数据生成：
    线号（group 拼 Service-LineNumber-NominalSize-NominalSpec）、阀门椭圆位号、仪表圈（两行：类别/回路号）、
    设备位号（下划线）、仪表/PLC/联锁圈内文字、跨图连接器字母与去向
  text / table / poly / rect / sym / style 原样保留
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import symbol_geom  # noqa: E402

try:
    STYLE_SCALES = json.loads((Path(__file__).resolve().parent.parent / 'assets' / 'plant_style_scales.json').read_text(encoding='utf-8'))
except Exception:
    STYLE_SCALES = {}
GEOM = symbol_geom.load()      # 非智能对象几何库（手工新增符号默认用它；--geom-all 时 Plant 库符号也用它）
GEOM_ALL = False

INSTR = {'Field Mounted Discrete Instrument Style', 'Primary Loc Accessible PLC Style',
         'Field Mounted Discrete Hardware Interlock Style', 'Primary Loc Accessible Discrete Instrument Style',
         'Field Mounted PLC Style'}
# 图层：颜色（ACI）、线宽（0.01 mm）、线型。实体一律“随层”，线宽/颜色/线型只由图层决定，
# 这样在 AutoCAD 里改图层即可整体调整；PDF 为黑白时按线宽区分层次
LAYERS = [
    {'name': '管线-主', 'color': 1, 'lw': 70},                       # 主工艺管线 0.70，红
    {'name': '管线-次', 'color': 2, 'lw': 35},                       # 仪表接管、取样、排凝支线 0.35，黄
    {'name': '信号-电', 'color': 4, 'lw': 18, 'ltype': 'DASHED2'},   # 电信号、气动信号 0.18，青，虚线
    {'name': '信号-软件', 'color': 6, 'lw': 18},                     # 软件/通讯链路 0.18，洋红，实线+小圆
    {'name': '符号', 'color': 7, 'lw': 35},                          # 阀门、仪表、设备、管嘴、连接器、箭头 0.35
    {'name': '位号', 'color': 3, 'lw': 25},                          # 位号、线号、仪表圈、椭圆 0.25，绿
]
LINES = {
    'Primary Style': dict(layer='管线-主'),
    'Secondary Style': dict(layer='管线-次'),
    'Electrical Style': dict(layer='信号-电'),
    'Software Style': dict(layer='信号-软件', circle=True),
    'Pneumatic Style': dict(layer='信号-电'),
}
ARROW_STYLE, ARROW_LEN = 'Flow Arrow Style', 4.7
NECK, FLANGE_GAP, FLANGE_LEN = 3.0, 1.0, 5.2    # 管嘴：接管长度、法兰对间距、法兰线长（mm）
GAP = 1.4            # 线交叉处打断：每侧留 1.4 mm（共 2.8 mm）
RANK = {'信号-电': 0, '信号-软件': 0, '管线-次': 1, '管线-主': 2}   # 交叉时优先打断数字小（线宽更细）的线
R_BUBBLE = 5.0
H_TAG, H_LINE, H_EQ, H_BUB, H_OPC_L, H_OPC_D = 2.5, 2.5, 3.5, 2.4, 3.0, 2.0
ON_LINE, OFF_V, OFF_H = 1.2, 1.5, 1.2     # 线号标注点离线 < ON_LINE 视为落在线上；文字基线离线的距离（竖线 / 横线）
LAYER_TAG = '位号'


def rot(dx, dy, deg):
    a = math.radians(deg)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def seglen(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def path_len(V):
    return sum(seglen(V[i], V[i + 1]) for i in range(len(V) - 1))


def project(V, p):
    """p 在折线 V 上的最近点：返回 (弧长, 距离, 所在段序号)"""
    best, acc = (0.0, 1e9, 0), 0.0
    for i in range(len(V) - 1):
        a, b = V[i], V[i + 1]
        L = seglen(a, b)
        if L < 1e-9:
            continue
        t = max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)))
        q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        d = seglen(p, q)
        if d < best[1]:
            best = (acc + t * L, d, i)
        acc += L
    return best


def subpath(V, s0, s1):
    """折线上弧长 s0~s1 的一段"""
    out, acc = [], 0.0
    for i in range(len(V) - 1):
        a, b = V[i], V[i + 1]
        L = seglen(a, b)
        lo, hi = acc, acc + L
        if hi <= s0 or lo >= s1 or L < 1e-9:
            acc = hi
            continue
        ta, tb = max(s0, lo) - lo, min(s1, hi) - lo
        pa = [a[0] + (b[0] - a[0]) * ta / L, a[1] + (b[1] - a[1]) * ta / L]
        pb = [a[0] + (b[0] - a[0]) * tb / L, a[1] + (b[1] - a[1]) * tb / L]
        if not out:
            out.append(pa)
        out.append(pb)
        acc = hi
    return out


def seg_cross(a, b, c, d, eps=0.6):
    """线段 ab 与 cd 的内部交点（两线段端点附近 eps 内不算，T 形接头和端点相接不处理）；返回 (点, t_ab, t_cd) 或 None"""
    r = (b[0] - a[0], b[1] - a[1]); s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return None
    qp = (c[0] - a[0], c[1] - a[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / den
    u = (qp[0] * r[1] - qp[1] * r[0]) / den
    L1, L2 = math.hypot(*r), math.hypot(*s)
    if not (eps / L1 < t < 1 - eps / L1 and eps / L2 < u < 1 - eps / L2):
        return None
    return (a[0] + t * r[0], a[1] + t * r[1]), t, u


def circle(cx, cy, r, n=36):
    return [[cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)] for k in range(n)]


def stadium(cx, cy, w, h, n=10):
    r = h / 2
    pts = []
    for k in range(n + 1):
        a = -math.pi / 2 + math.pi * k / n
        pts.append([cx + w / 2 - r + r * math.cos(a), cy + r * math.sin(a)])
    for k in range(n + 1):
        a = math.pi / 2 + math.pi * k / n
        pts.append([cx - w / 2 + r + r * math.cos(a), cy + r * math.sin(a)])
    return pts


def text_w(s, h):
    """文字宽度估计：数字/大写 0.62h，汉字 1.0h"""
    return sum(h * (1.0 if ord(c) > 255 else 0.62) for c in s)


class Conv:
    def __init__(self, cat):
        self.cat = cat

    def conn_pts(self, it):
        """内联符号两端连接点（绝对坐标）；目录无连接点时取外框左右中点"""
        st = it.get('style') or it.get('body')
        c = self.cat.get(st) or {}
        att = c.get('att') or []
        if len(att) >= 2:
            pa, pb = att[0], att[-1]
        else:
            bb = c.get('bbox') or [-4, -2, 4, 2]
            pa, pb = [bb[0], 0], [bb[2], 0]
        r = it.get('rot', 0)
        x, y = it['at']
        f = 1.0       # 符号按 spec 里的 scale 缩放时，连接点同比移动（Plant 库符号 scale 是绝对比例，手工符号是倍数）
        if 'scale' in it:
            if (GEOM.get(st) or {}).get('native'):
                f = float(it['scale'])
            else:
                f = float(it['scale']) / float((STYLE_SCALES.get(st) or {}).get('scale') or it['scale'])
        out = []
        for p in (pa, pb):
            p = [p[0] * f, p[1] * f]
            dx, dy = rot(p[0], p[1], r)
            out.append([x + dx, y + dy])
        return out

    def bbox_half(self, it):
        st = it.get('style') or it.get('body')
        bb = (self.cat.get(st) or {}).get('bbox') or [-4, -2, 4, 2]
        return max(abs(bb[0]), abs(bb[2])), max(abs(bb[1]), abs(bb[3]))

    def convert(self, items):
        out, byid = [], {}
        for it in items:
            if it.get('id'):
                byid[it['id']] = it
        # 内联连接：线 id → [资产 id]
        inline = {}
        for it in items:
            if it['k'] == 'connect' and it.get('ctx') == 'inline':
                inline.setdefault(it['line'], []).append(it['asset'])
        self.cross = self.find_crossings(items)
        self.nozzles = [(n['at'], n.get('rot', 0)) for n in items if n['k'] == 'nozzle']
        self.native_polys = []
        syms, polys, texts = [], [], []
        for it in items:
            k = it['k']
            if k in ('connect', 'tee', 'opc'):
                continue
            if k == 'nozzle':
                self.nozzle(it, polys)
                continue
            if k == 'asset':
                self.asset(it, syms, texts)
            elif k == 'cv':
                self.cv(it, syms, texts)
            elif k == 'line':
                self.line(it, byid, inline, polys, syms, texts)
            elif k == 'sym' and (GEOM.get(it['style']) or {}).get('native'):
                self.sym(it['style'], it, syms)      # 图例里直接写的手工新增符号：画成折线
            else:
                out.append(it)
        return out + polys + self.native_polys + syms + texts

    def find_crossings(self, items):
        """全部管线两两求交；返回 {线 id: [交点弧长…]}（只记需要在该线上打断的）"""
        L = [(it['id'], [list(p) for p in it['pts']], LINES[it['style']]['layer']) for it in items if it['k'] == 'line']
        out = {}
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                (ia, Va, la), (ib, Vb, lb) = L[i], L[j]
                acc_a = 0.0
                for m in range(len(Va) - 1):
                    la_seg = seglen(Va[m], Va[m + 1])
                    acc_b = 0.0
                    for n in range(len(Vb) - 1):
                        lb_seg = seglen(Vb[n], Vb[n + 1])
                        x = seg_cross(Va[m], Va[m + 1], Vb[n], Vb[n + 1])
                        if x:
                            pt, ta, tb = x
                            ra, rb = RANK[la], RANK[lb]
                            if ra != rb:
                                brk_a = ra < rb
                            else:   # 同级：打断横线
                                horiz_a = abs(Va[m + 1][0] - Va[m][0]) >= abs(Va[m + 1][1] - Va[m][1])
                                horiz_b = abs(Vb[n + 1][0] - Vb[n][0]) >= abs(Vb[n + 1][1] - Vb[n][1])
                                if horiz_a == horiz_b:
                                    continue
                                brk_a = horiz_a
                            if brk_a:
                                out.setdefault(ia, []).append(acc_a + ta * la_seg)
                            else:
                                out.setdefault(ib, []).append(acc_b + tb * lb_seg)
                        acc_b += lb_seg
                    acc_a += la_seg
        return out

    def nozzle(self, it, polys):
        """管嘴：自设备壁沿 rot 方向伸出一小段接管，端部画一对法兰线（符号层）"""
        x, y = it['at']
        r = math.radians(it.get('rot', 0))
        dx, dy = math.cos(r), math.sin(r)
        px, py = -dy, dx
        polys.append({'k': 'poly', 'pts': [[round(x, 3), round(y, 3)], [round(x + dx * (NECK + FLANGE_GAP), 3), round(y + dy * (NECK + FLANGE_GAP), 3)]], 'layer': '符号'})
        for off in (NECK, NECK + FLANGE_GAP):
            cx, cy = x + dx * off, y + dy * off
            polys.append({'k': 'poly', 'pts': [[round(cx - px * FLANGE_LEN / 2, 3), round(cy - py * FLANGE_LEN / 2, 3)],
                                               [round(cx + px * FLANGE_LEN / 2, 3), round(cy + py * FLANGE_LEN / 2, 3)]], 'layer': '符号'})

    # ------------------------------------------------------------------ 符号与位号
    def sym(self, style, it, syms):
        g = GEOM.get(style)
        if g is not None and (g.get('native') or GEOM_ALL):
            # 非智能对象几何库：直接画成折线，不依赖项目里的符号样式
            for pa in symbol_geom.polys(style, it['at'], it.get('rot', 0), it.get('scale', 1.0)):
                self.native_polys.append({'k': 'poly', 'pts': pa['pts'], 'layer': '符号', **({'closed': True} if pa['closed'] and len(pa['pts']) > 3 else {})})
            return
        d = {'k': 'sym', 'style': style, 'at': it['at'], 'rot': it.get('rot', 0), 'layer': '符号'}
        if 'scale' in it:
            d['scale'] = it['scale']
        syms.append(d)

    def asset(self, it, syms, texts):
        st = it['style']
        self.sym(st, it, syms)
        tag = it['id']
        an = it.get('anno')
        if st == 'Off Page Connector Style':
            self.opc_text(it, texts)
        elif st in INSTR and not an:
            self.bubble_text(tag, it['at'], texts)
        if an:
            self.anno(an, it, texts)

    def cv(self, it, syms, texts):
        self.sym(it['body'], it, syms)
        self.sym(it['act'], it, syms)
        if it.get('anno'):
            self.anno(it['anno'], it, texts)

    def bubble_text(self, tag, c, texts):
        a, b = (tag.split('-', 1) + [''])[:2] if '-' in tag else (tag, '')
        if not b:
            texts.append(self.t(c, a, H_BUB, 'MC'))
            return
        texts.append(self.t([c[0], c[1] + 1.5], a, H_BUB, 'MC'))
        texts.append(self.t([c[0], c[1] - 1.5], b, H_BUB, 'MC'))

    def t(self, at, s, h, just='MC', rot_=0):
        d = {'k': 'text', 'at': [round(at[0], 3), round(at[1], 3)], 'text': s, 'h': h, 'just': just, 'layer': LAYER_TAG}
        if rot_:
            d['rot'] = rot_
        return d

    def anno(self, an, it, texts):
        st, at = an['style'], an['at']
        tag = it['id']
        if st == 'Oval Tag Style':
            w = text_w(tag, H_TAG) + 4.0
            texts.append({'k': 'poly', 'pts': [[round(x, 3), round(y, 3)] for x, y in stadium(at[0], at[1], w, 5.0)], 'closed': True, 'layer': LAYER_TAG})
            texts.append(self.t(at, tag, H_TAG, 'MC'))
        elif st == 'Equipment Tag':
            texts.append(self.t(at, '\\L' + tag + '\\l', H_EQ, 'MC'))
        else:   # 仪表圈
            texts.append({'k': 'poly', 'pts': [[round(x, 3), round(y, 3)] for x, y in circle(at[0], at[1], R_BUBBLE)], 'closed': True, 'layer': LAYER_TAG})
            self.bubble_text(tag, at, texts)
            # 圈到符号的细连线：从圈边画到符号外框边，沿圈心到外框中心的连线（外框按旋转和比例换算）
            x0, y0, x1, y1 = self.world_box(it)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            dx, dy = cx - at[0], cy - at[1]
            d = math.hypot(dx, dy)
            if d > R_BUBBLE + 0.5:
                ux, uy = dx / d, dy / d
                tin = 0.0
                for o, u, lo, hi in ((at[0], ux, x0, x1), (at[1], uy, y0, y1)):
                    if abs(u) > 1e-9:
                        ta, tb = (lo - o) / u, (hi - o) / u
                        tin = max(tin, min(ta, tb))
                p0 = [at[0] + ux * R_BUBBLE, at[1] + uy * R_BUBBLE]
                p1 = [at[0] + ux * tin, at[1] + uy * tin]
                if seglen(p0, p1) > 0.3:
                    texts.append({'k': 'poly', 'pts': [[round(v, 3) for v in p0], [round(v, 3) for v in p1]], 'layer': LAYER_TAG})

    def world_box(self, it):
        """符号外框（世界坐标，含旋转和 spec 里的比例）"""
        st = it.get('style') or it.get('body')
        bb = (self.cat.get(st) or {}).get('bbox') or [-4, -2, 4, 2]
        f = 1.0
        if 'scale' in it:
            if (GEOM.get(st) or {}).get('native'):
                f = float(it['scale'])
            else:
                f = float(it['scale']) / float((STYLE_SCALES.get(st) or {}).get('scale') or it['scale'])
        r = it.get('rot', 0)
        cs = [rot(dx * f, dy * f, r) for dx, dy in ((bb[0], bb[1]), (bb[2], bb[3]), (bb[0], bb[3]), (bb[2], bb[1]))]
        x, y = it['at']
        return (x + min(c[0] for c in cs), y + min(c[1] for c in cs), x + max(c[0] for c in cs), y + max(c[1] for c in cs))

    def opc_text(self, it, texts):
        props = it.get('props', {})
        r = it.get('rot', 0) % 360
        x, y = it['at']
        letter, dest = props.get('ConnectorNumber', ''), props.get('OriginOrDestination', '')
        dx, dy = rot(6.9, 0, r)
        texts.append(self.t([x + dx, y + dy], letter, H_OPC_L, 'MC'))
        ref = dest.split()[0] if dest.startswith('P&ID') else ''
        if ref:
            dx, dy = rot(26.5, 0, r)
            texts.append(self.t([x + dx, y + dy], ref, H_TAG, 'MC', 90 if r in (90, 270) else 0))
        if dest:
            w = text_w(dest, H_OPC_D)
            if r in (0, 180):
                just_dn, sgn_dn = ('TL', -1) if r == 0 else ('BR', 1)
                # 默认放在连接器背向侧；若落进标题栏/修订栏区域就翻到另一侧
                x0, x1 = (x, x + w) if r == 0 else (x - w, x)
                y_dn = y + sgn_dn * 4.8
                if self.in_tb(x0, x1, min(y_dn, y_dn - 2.4), max(y_dn, y_dn + 2.4)):
                    just_dn = {'TL': 'BL', 'BR': 'TR'}[just_dn]
                    y_dn = y - sgn_dn * 4.8
                texts.append(self.t([x, y_dn], dest, H_OPC_D, just_dn))
            else:
                sgn = 1 if r == 90 else -1
                yy = y + sgn * 21
                if self.in_tb(x + 4.5, x + 4.5 + w, yy - 2, yy + 2):
                    texts.append(self.t([x - 4.5, yy], dest, H_OPC_D, 'MR'))
                else:
                    texts.append(self.t([x + 4.5, yy], dest, H_OPC_D, 'ML'))

    @staticmethod
    def in_tb(x0, x1, y0, y1):
        return x1 > 235.0 and y0 < 91.0

    # ------------------------------------------------------------------ 管线
    def line(self, it, byid, inline, polys, syms, texts):
        sty = LINES[it['style']]
        V = [list(p) for p in it['pts']]
        total = path_len(V)
        cuts = []
        for aid in inline.get(it['id'], []):
            a = byid[aid]
            p0, p1 = self.conn_pts(a)
            s0, s1 = project(V, p0)[0], project(V, p1)[0]
            cuts.append((min(s0, s1), max(s0, s1)))
        for s in self.cross.get(it['id'], []):
            cuts.append((s - GAP, s + GAP))
        cuts.sort()
        pieces, cur = [], 0.0
        for s0, s1 in cuts:
            if s0 - cur > 0.2:
                pieces.append((cur, s0))
            cur = max(cur, s1)
        if total - cur > 0.2:
            pieces.append((cur, total))
        for s0, s1 in pieces:
            pts = subpath(V, s0, s1)
            if len(pts) >= 2:
                polys.append({'k': 'poly', 'pts': [[round(v, 3) for v in p] for p in pts], 'layer': sty['layer']})
        # 流向箭头：Primary 线只在末段放一个（流入方向）。末段上有朝向来流的管嘴（线在管嘴处或穿过器壁继续到设备内部）时，
        # 箭头尖放在该管嘴法兰外侧；否则放在线端
        if it['style'] == 'Primary Style' and len(V) >= 2 and not it.get('noarrow'):
            a, b = V[-2], V[-1]
            L = seglen(a, b)
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t_tip = L
            for (nx, ny), nr in self.nozzles:
                t = (nx - a[0]) * ux + (ny - a[1]) * uy
                off = abs(-(nx - a[0]) * uy + (ny - a[1]) * ux)
                ox, oy = math.cos(math.radians(nr)), math.sin(math.radians(nr))
                if off < 0.8 and 0.5 < t <= L + 0.8 and ox * ux + oy * uy < -0.9:
                    t_tip = min(t_tip, t - (NECK + FLANGE_GAP + 0.4)) if t_tip < L else t - (NECK + FLANGE_GAP + 0.4)
            s_tip = total - L + t_tip
            if t_tip - ARROW_LEN >= 1.0 and not any(c0 < s_tip and c1 > s_tip - ARROW_LEN for c0, c1 in cuts):
                ang = math.degrees(math.atan2(uy, ux))
                syms.append({'k': 'sym', 'style': ARROW_STYLE, 'at': [round(a[0] + ux * (t_tip - ARROW_LEN), 3), round(a[1] + uy * (t_tip - ARROW_LEN), 3)], 'rot': round(ang, 3), 'layer': '符号'})
        # 信号线（软件/通讯）中点小圆
        if sty.get('circle') and total > 3:
            mid = subpath(V, total / 2 - 0.01, total / 2 + 0.01)
            cx, cy = ((mid[0][0] + mid[-1][0]) / 2, (mid[0][1] + mid[-1][1]) / 2)
            polys.append({'k': 'poly', 'pts': [[round(x, 3), round(y, 3)] for x, y in circle(cx, cy, 1.0, 16)], 'closed': True, 'layer': '信号-软件'})
        # 线号
        g, an = it.get('group'), it.get('anno')
        if g and an:
            txt = '-'.join(str(g.get(k, '')) for k in ('Service', 'LineNumber', 'NominalSize', 'NominalSpec'))
            s, dist, seg = project(V, an)
            a, b = V[seg], V[seg + 1]
            vertical = abs(b[0] - a[0]) < abs(b[1] - a[1])
            if dist < ON_LINE:   # 标注点落在线上：沿线贴着线的上方（竖线贴左侧）
                if vertical:
                    texts.append(self.t([an[0] - OFF_V, an[1]], txt, H_LINE, 'BC', 90))
                else:
                    texts.append(self.t([an[0], an[1] + OFF_H], txt, H_LINE, 'BC'))
            else:
                texts.append(self.t(an, txt, H_LINE, 'MC', 90 if vertical else 0))


def main(argv):
    global GEOM_ALL
    cats, args, i = [], [], 0
    while i < len(argv):
        if argv[i] == '--catalog':
            cats.append(argv[i + 1]); i += 2; continue
        if argv[i] == '--geom-all':
            GEOM_ALL = True; i += 1; continue
        args.append(argv[i]); i += 1
    src, dst, sheets = Path(args[0]), Path(args[1]), args[2:]
    cat = {}
    for c in cats:
        cat.update(json.loads(Path(c).read_text(encoding='utf-8')))
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(dst.glob('*')):
        if f.is_file():
            f.unlink()
    conv = Conv(cat)
    n = 0
    for f in sorted(src.glob('*.json')):
        if f.name.endswith(('.ids.json',)) or f.stem.startswith('_'):
            continue
        if f.name.endswith('.props.json'):
            (dst / f.name).write_bytes(f.read_bytes())
            continue
        if sheets and f.stem not in sheets:
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        d['items'] = conv.convert(d['items'])
        have = {l['name'] for l in d.get('layers', [])}
        d['layers'] = d.get('layers', []) + [l for l in LAYERS if l['name'] not in have]
        (dst / f.name).write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        kinds = {}
        for it in d['items']:
            kinds[it['k']] = kinds.get(it['k'], 0) + 1
        print(f'{f.stem}: {kinds}')
        n += 1
    print('转换', n, '张 →', dst)


if __name__ == '__main__':
    main(sys.argv[1:])
