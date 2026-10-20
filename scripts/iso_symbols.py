"""ISO 10628-2:2012 风格的符号定义（自绘几何，按原件页面的形状和比例；不含标准的图形文件或页面截图）。
用途：profile 的 symbol_map 把 Plant 库符号换成这里的符号；也可在版面里直接用样式名。
约定：
  - 1 格 = 2.0 mm（ISO 网格 2.5 mm 的 0.8 倍，阀门 4 格宽 = 8 mm，与现有 Plant 阀门同大，换符号不改版面）。
  - 插入点在符号中心；ports 是管线连接点（相对插入点，mm）；在线件的 ports 与被替换的 Plant 符号一致。
  - block=True：转换时画成"一个块参照"（可整体移动/复制），不是散线。
  - basis：依据（标准、条号、登记号、PDF 页 / 印刷页）、是否已和原件逐个目测核对、备注。
    PDF 页比印刷页大 4（ISO 10628-2:2012 PDF 第 42 页 = 印刷第 38 页）。
命令行：python iso_symbols.py check   列出全部符号与依据（verified 统计）
"""
import math
import sys

from symbol_geom import P as _P, _circle


def P(pts, closed=False, fill=False):
    """闭合图形显式回到起点（转换器只在点数大于 3 时才按闭合折线画）"""
    pts = [tuple(p) for p in pts]
    if closed and pts[0] != pts[-1]:
        pts.append(pts[0])
    return _P(pts, closed, fill)

C = 2.0                      # 1 格 = 2 mm
STD = 'ISO 10628-2:2012'


def c(*pts):
    return [(x * C, y * C) for x, y in pts]


def circle(cx, cy, r, n=48):
    return _circle(cx * C, cy * C, r * C, n)


def arc(cx, cy, r, a0, a1, n=24, ry=None):
    """cx,cy,r 单位为格；a0→a1 度；ry 省略为圆"""
    ry = r if ry is None else ry
    return [((cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n))) * C, (cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) * C) for i in range(n + 1)]


def rect(x0, y0, x1, y1):
    return c((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def tri_l(w=2, h=1, fill=False):
    """左三角（底在左，尖在中心）"""
    return P(c((-w, h), (-w, -h), (0, 0)), True, fill)


def tri_r(w=2, h=1, fill=False):
    return P(c((w, h), (w, -h), (0, 0)), True, fill)


def bowtie(fill=False, w=2, h=1):
    return [tri_l(w, h, fill), tri_r(w, h, fill)]


def basis(item, reg, pdf, verified=True, note=''):
    return {'std': STD, 'item': item, 'reg': reg, 'pdf_page': pdf, 'printed_page': pdf - 4, 'verified': verified, 'note': note}


V_PORTS = {'in': (-4, 0), 'out': (4, 0)}


def _ball(closed):
    r = 0.9
    ps = []
    for sx in (-1, 1):       # 圆与三角斜边的交点
        # 斜边：(2sx,1)→(0,0)，参数 t∈[0,1]：x=2sx(1-t)，y=1-t ；|p|=r → (1-t)^2*(4+1)=r^2
        k = r / math.sqrt(5)
        ps.append(c((sx * 2 * k, k), (sx * 2, 1), (sx * 2, -1), (sx * 2 * k, -k)))
    out = [P(ps[0], False), P(ps[1], False), P(circle(0, 0, r), True, closed)]
    return out


def _valve(zh, item, reg, extra=None, closed=False, note='', use='', pdf=42, tris=True):
    paths = (bowtie(closed) if tris else []) + (extra or [])
    return dict(zh=zh, cat='手动阀', use=use or zh, ports=V_PORTS, paths=paths, block=True, basis=basis(item, reg, pdf, True, note))


def _spring(x, y0, n, amp, step):
    pts, y, left = [(x, y0)], y0, True
    for _ in range(n):
        y += step
        pts.append((x + (-amp if left else amp), y))
        left = not left
    pts.append((x, y + step))
    return pts


def _dashed(p0, p1, n=3):
    out = []
    for i in range(n):
        a, b = i / (n - 0.5), (i + 0.55) / (n - 0.5)
        out.append(P([(p0[0] + (p1[0] - p0[0]) * a, p0[1] + (p1[1] - p0[1]) * a), (p0[0] + (p1[0] - p0[0]) * b, p0[1] + (p1[1] - p0[1]) * b)]))
    return out


def _grid_box(x0, y0, x1, y1, cols, rows):
    ps = [P(rect(x0, y0, x1, y1), True)]
    for i in range(1, cols):
        x = x0 + (x1 - x0) * i / cols
        ps.append(P(c((x, y0), (x, y1))))
    for j in range(1, rows):
        y = y0 + (y1 - y0) * j / rows
        ps.append(P(c((x0, y), (x1, y))))
    return ps


def _compressor_lines(r=3.0):
    pts = []
    for sgn in (1, -1):
        a = (r * math.cos(math.radians(133)), sgn * r * math.sin(math.radians(133)))
        b = (r * math.cos(math.radians(29)), sgn * r * math.sin(math.radians(29)))
        pts.append(P(c(a, b)))
    return pts


def _chevron(r):
    return P(c((0, r), (r, 0), (0, -r)))


def _blades(r=2.1, half=24):
    out = []
    for k in range(3):
        a = 90 + 120 * k
        pts = [(0, 0)] + [(0.8 * r * math.cos(math.radians(a + d)) , 0.8 * r * math.sin(math.radians(a + d))) for d in (-half, 0)]
        pts = [(0, 0), (0.62 * r * math.cos(math.radians(a - half)), 0.62 * r * math.sin(math.radians(a - half))), (r * math.cos(math.radians(a)), r * math.sin(math.radians(a))),
               (0.62 * r * math.cos(math.radians(a + half)), 0.62 * r * math.sin(math.radians(a + half)))]
        out.append(P(c(*pts), True))
    return out


def _letter_m(s=0.7):
    return P(c((-s, -s), (-s, s), (0, 0.1), (s, s), (s, -s)))


def _vessel_v(w=4.0, h=7.0, d=1.5):
    """立式容器：半宽 w 格、半高 h 格（含封头）、封头深 d 格（椭圆）"""
    top = arc(0, h - d, w, 0, 180, 24, ry=d)
    bot = arc(0, -(h - d), w, 180, 360, 24, ry=d)
    return [P(top + bot, True)]


def _vessel_h(w=7.0, h=4.0, d=1.5):
    left = arc(-(w - d), 0, d, 90, 270, 24, ry=h)
    right = arc(w - d, 0, d, -90, 90, 24, ry=h)
    return [P(right + left, True)]


ISO_DEFS = {}
_D = ISO_DEFS

# ------------------------------------------------------------------ 阀门（ISO 10628-2 表 2 第 21、22 组）
_D['ISO Valve General Style'] = _valve('阀门（通用）', '21.1', '2101', use='未指明型式的阀', pdf=41)
_D['ISO Globe Valve Style'] = _valve('截止阀', '21.4', 'X8068', [P(circle(0, 0, 0.35), True, True)], use='截止阀（开）')
_D['ISO Globe Valve Closed Style'] = _valve('截止阀（关）', '21.4', 'X8068', closed=True, note='关位用实心表示，是项目约定，不是 ISO 条文')
_D['ISO Ball Valve Style'] = _valve('球阀', '21.7', 'X8071', _ball(False), tris=False, use='球阀（开）')
_D['ISO Ball Valve Closed Style'] = _valve('球阀（关）', '21.7', 'X8071', _ball(True), tris=False, note='关位用实心球表示，是项目约定，不是 ISO 条文')
_D['ISO Gate Valve Style'] = _valve('闸阀', '21.10', 'X8074', [P(c((0, -1), (0, 1)))], use='闸阀（开）')
_D['ISO Gate Valve Closed Style'] = _valve('闸阀（关）', '21.10', 'X8074', [P(c((0, -1), (0, 1)))], closed=True, note='关位用实心表示，是项目约定')
_D['ISO Butterfly Valve Style'] = _valve('蝶阀', '21.11', 'X8075', [P(c((0, -1), (0, 1))), P(circle(0, 0, 0.5), True, True)], use='蝶阀（形式 1）')
_D['ISO Needle Valve Style'] = _valve('针阀', '21.13', 'X8076', [P(c((-0.5, 1.9), (0.5, 1.9), (0, 0.9)), True, True)], use='针阀（开）')
_D['ISO Needle Valve Closed Style'] = _valve('针阀（关）', '21.13', 'X8076', [P(c((-0.5, 1.9), (0.5, 1.9), (0, 0.9)), True, True)], closed=True, note='关位用实心表示，是项目约定')
_D['ISO Check Valve Style'] = dict(zh='止回阀', cat='手动阀', use='止回阀（通用）。实心点一侧的流向含义未核对原件文字，暂不自动替换 PIP 止回阀', ports=V_PORTS, block=True,
                                  paths=bowtie(False) + [P(circle(-2, 1, 0.55), True, True)], basis=basis('22.1', 'X8077', 43, True, '图形已核对；实心点与流向的对应关系原件页面未写明，使用前先确认'))

# ------------------------------------------------------------------ 安全与阻火（第 23 组），端口与 QMZ 安全阀一致（±5 mm）
_D['ISO Safety Valve Style'] = dict(zh='弹簧安全阀', cat='减压与安全', use='弹簧式安全阀（直立：弹簧在上，入口在左、出口在右）', ports={'in': (-5, 0), 'out': (5, 0)}, block=True, paths=[
    P([(-5, 2.5), (-5, -2.5), (0, 0)], True), P([(0, 0), (5, 2.25), (5, -2.25)], True), P([(3.3, 2.0), (3.9, 2.0), (3.9, -2.0), (3.3, -2.0)], True, True),
    P(circle(0, 0, 0.55 * 1.25), True, True), P(_spring(0, 0.8, 5, 1.6, 1.5) + [(0, 9.5)])],
    basis=basis('23.1', 'X2124', 43, True, '按 2.5 mm 网格画（端口 ±5 mm）；弹簧圈数按版面取舍'))
_D['ISO Rupture Disc Style'] = dict(zh='爆破片', cat='减压与安全', use='爆破片（在线）', ports={'in': (-4, 0), 'out': (4, 0)}, block=True, paths=[
    P(c((-1, 2), (1, 2), (1, -2), (-1, -2)), True), P(c((-0.6, 2), (-0.6, 1)) + arc(-0.6, 0, 1, 90, -90, 16) + c((-0.6, -1), (-0.6, -2))),
    P(c((-2, 0), (-1, 0))), P(c((1, 0), (2, 0)))], basis=basis('23.3', 'X8080', 43, False, '形状按页面目测，未逐点比对'))
_D['ISO Flame Arrestor Style'] = dict(zh='阻火器', cat='减压与安全', use='阻火器（在线，格栅）', ports={'in': (-7.5, 0), 'out': (7.5, 0)}, block=True,
                                     paths=_grid_box(-1, -2, 1, 2, 2, 4) + [P([(-7.5, 0), (-2, 0)]), P([(2, 0), (7.5, 0)])], basis=basis('23.4', '2036', 43, True))
_D['ISO Flame Arrestor Detonation Style'] = dict(zh='爆轰阻火器', cat='减压与安全', use='防爆轰阻火器', ports={'in': (-7.5, 0), 'out': (7.5, 0)}, block=True,
                                                paths=_grid_box(-3, -4, 1, 4, 3, 4) + [P(c((1, 2), (3, 0), (1, -2))), P([(-7.5, 0), (-6, 0)]), P([(6, 0), (7.5, 0)])],
                                                basis=basis('23.6', 'C0088', 43, False, '形状按页面目测'))

# ------------------------------------------------------------------ 管件（第 24 组）
_D['ISO Strainer Style'] = dict(zh='过滤器（管道）', cat='过滤', use='管道过滤器/粗滤器（斜虚线）', ports={'in': (-4, 0), 'out': (4, 0)}, block=True,
                               paths=[P(c((-1, -2), (1, -2), (1, 2), (-1, 2)), True)] + _dashed(c((-1, 2))[0], c((1, -2))[0], 3) + [P([(-4, 0), (-2, 0)]), P([(2, 0), (4, 0)])],
                               basis=basis('24.6', 'X8090', 44, True))
_D['ISO Compensator Style'] = dict(zh='补偿器（膨胀节）', cat='管件与连接', use='管道补偿器', ports={'in': (-4, 0), 'out': (4, 0)}, block=True,
                                  paths=[P(arc(1.5, 0, 2.5, 126.87, 233.13, 16)), P(arc(-1.5, 0, 2.5, -53.13, 53.13, 16)), P([(-4, 0), (-2, 0)]), P([(2, 0), (4, 0)])],
                                  basis=basis('24.5', '533', 44, False, '透镜形按页面目测'))
_D['ISO Reducer Style'] = dict(zh='异径管', cat='管件与连接', use='同心异径管（尖端朝小口）', ports={'in': (-4, 0), 'out': (4, 0)}, block=True,
                              paths=[P(c((-1.2, 1), (1.2, 0), (-1.2, -1)), True), P([(-4, 0), (-2.4, 0)]), P([(2.4, 0), (4, 0)])], basis=basis('24.17', '516', 45, True))
_D['ISO Flanged Connection Style'] = dict(zh='法兰连接', cat='管嘴与法兰', use='法兰连接（两短竖线）', ports={'in': (-4, 0), 'out': (4, 0)}, block=True,
                                         paths=[P(c((-0.3, -1), (-0.3, 1))), P(c((0.3, -1), (0.3, 1))), P([(-4, 0), (-0.6, 0)]), P([(0.6, 0), (4, 0)])], basis=basis('24.16', '511', 45, True))
_D['ISO Viewing Glass Style'] = dict(zh='视镜', cat='流量与测量元件', use='视镜', ports={'in': (-4, 0), 'out': (4, 0)}, block=True,
                                    paths=[P(c((-1.5, -1), (1.5, -1), (1.5, 1), (-1.5, 1)), True), P(circle(0, 0, 0.8), True), P([(-4, 0), (-3, 0)]), P([(3, 0), (4, 0)])],
                                    basis=basis('24.1', '2034', 44, True))
_D['ISO Hose Style'] = dict(zh='软管', cat='管件与连接', use='软管（波形）', ports={'in': (-10, 0), 'out': (10, 0)}, block=True,
                           paths=[P([(-10, 0)] + [(-8 + 16 * i / 48, 1.1 * math.sin(math.pi * 2 * 2.5 * i / 48)) for i in range(49)] + [(10, 0)])],
                           basis=basis('24.18', 'X411', 45, False, '波形按页面目测'))

# ------------------------------------------------------------------ 泵、压缩机、风机、电机（第 15–17、20 组）
_PR = 3.25
_D['ISO Pump Style'] = dict(zh='液体泵（通用）', cat='泵与压缩机', use='液体泵，通用；入口左、出口右', ports={'in': (-_PR * C, 0), 'out': (_PR * C, 0)}, block=True,
                           paths=[P(circle(0, 0, _PR), True), _chevron(_PR)], basis=basis('15.1', '2301', 35, True))
_D['ISO Centrifugal Pump Style'] = dict(zh='离心泵', cat='泵与压缩机', use='离心泵', ports={'in': (-_PR * C, 0), 'out': (_PR * C, 0)}, block=True,
                                       paths=[P(circle(0, 0, _PR), True), _chevron(_PR), P(c((-_PR, 0), (_PR, 0)))], basis=basis('15.2', '2322', 35, True))
_D['ISO Gear Pump Style'] = dict(zh='齿轮泵', cat='泵与压缩机', use='齿轮泵', ports={'in': (-_PR * C, 0), 'out': (_PR * C, 0)}, block=True,
                                paths=[P(circle(0, 0, _PR), True), _chevron(_PR), P(circle(-0.8, 0, 1.1), True), P(circle(0.8, 0, 1.1), True)], basis=basis('15.3', 'X8091', 35, False, '两个小圆按页面目测'))
_D['ISO Piston Pump Style'] = dict(zh='往复柱塞泵', cat='泵与压缩机', use='往复式柱塞泵', ports={'in': (-_PR * C, 0), 'out': (_PR * C, 0)}, block=True,
                                  paths=[P(circle(0, 0, _PR), True), _chevron(_PR), P(c((-0.6, -1), (-0.6, 1))), P(c((-0.6, 0), (1.2, 0)))], basis=basis('15.6', 'X8094', 35, False))
_D['ISO Compressor Style'] = dict(zh='压缩机/真空泵（通用）', cat='泵与压缩机', use='压缩机、真空泵（通用）；入口左、出口右（收口侧为高压）', ports={'in': (-3 * C, 0), 'out': (3 * C, 0)}, block=True,
                                 paths=[P(circle(0, 0, 3.0), True)] + _compressor_lines(), basis=basis('16.1', '2302', 36, True))
_D['ISO Centrifugal Compressor Style'] = dict(zh='离心压缩机', cat='泵与压缩机', use='离心压缩机', ports={'in': (-3 * C, 0), 'out': (3 * C, 0)}, block=True,
                                             paths=[P(circle(0, 0, 3.0), True)] + _compressor_lines() + [P(c((-3, 0), (3, 0)))], basis=basis('16.2', 'X8179', 36, True))
_D['ISO Piston Compressor Style'] = dict(zh='往复压缩机', cat='泵与压缩机', use='往复式压缩机', ports={'in': (-3 * C, 0), 'out': (3 * C, 0)}, block=True,
                                        paths=[P(circle(0, 0, 3.0), True)] + _compressor_lines() + [P(c((-0.6, -0.9), (-0.6, 0.9))), P(c((-0.6, 0), (1.2, 0)))], basis=basis('16.3', 'X8097', 36, True))
_D['ISO Fan Style'] = dict(zh='风机/鼓风机', cat='泵与压缩机', use='风机、鼓风机（三叶）', ports={'in': (-3 * C, 0), 'out': (3 * C, 0)}, block=True,
                          paths=[P(circle(0, 0, 3.0), True)] + _compressor_lines() + _blades(), basis=basis('17.1', 'X8164', 37, False, '叶片简化为三段弧'))
_D['ISO Electric Motor Style'] = dict(zh='电动机', cat='设备', use='电动机（圆内 M）；轴接口左右', ports={'shaft_l': (-4, 0), 'shaft_r': (4, 0)}, block=True,
                                     paths=[P(circle(0, 0, 2.0), True), _letter_m()], basis=basis('20.6', 'C0082', 41, True, '字母 M 用折线画'))

# ------------------------------------------------------------------ 换热器（第 3 组）
_D['ISO Heat Exchanger Fixed Tube Style'] = dict(zh='固定管板换热器', cat='换热器', use='直管换热器（固定管板）；壳程接口上右/下左，管程接口上左/下右', block=True,
                                                ports={'t_in': (-5.2 * C, 1.75 * C), 's_in': (3.5 * C, 1.75 * C), 's_out': (-3.5 * C, -1.75 * C), 't_out': (5.2 * C, -1.75 * C)},
                                                paths=[P(c((-6, -1.75), (6, -1.75), (6, 1.75), (-6, 1.75)), True), P(c((-4.3, -1.75), (-4.3, 1.75))), P(c((4.3, -1.75), (4.3, 1.75)))]
                                                + [P(c((-4.3, y), (4.3, y))) for y in (-0.9, 0, 0.9)]
                                                + [P(c((x, 1.75), (x, 3.0))) for x in (-5.2, 3.5)] + [P(c((x, -1.75), (x, -3.0))) for x in (-3.5, 5.2)],
                                                basis=basis('3.3', '2511', 15, True, '接口位置按页面目测'))
_D['ISO Heat Exchanger U-Tube Style'] = dict(zh='U 形管换热器', cat='换热器', use='U 形管换热器', block=True,
                                            ports={'t_in': (-5.2 * C, 1.75 * C), 't_out': (-3.5 * C, 1.75 * C), 's_in': (3.5 * C, 1.75 * C), 's_out': (5.2 * C, -1.75 * C)},
                                            paths=[P(c((-6, -1.75), (6, -1.75), (6, 1.75), (-6, 1.75)), True), P(c((-4.3, -1.75), (-4.3, 1.75))), P(c((-6, 0), (-4.3, 0))),
                                                   P(c((-4.3, 0.6), (3.5, 0.6)) + arc(3.5, 0, 0.6, 90, -90, 10) + c((-4.3, -0.6)))]
                                            + [P(c((x, 1.75), (x, 3.0))) for x in (-5.2, -3.5, 3.5)] + [P(c((5.2, -1.75), (5.2, -3.0)))],
                                            basis=basis('3.5', '2513', 15, False, 'U 形管走向按页面目测'))
_D['ISO Plate Heat Exchanger Style'] = dict(zh='板式换热器', cat='换热器', use='板式换热器（矩形 + X）', block=True,
                                           ports={'in_a': (-4.5 * C, 2 * C), 'out_a': (-4.5 * C, -2 * C), 'in_b': (4.5 * C, -2 * C), 'out_b': (4.5 * C, 2 * C)},
                                           paths=[P(c((-5, -2), (5, -2), (5, 2), (-5, 2)), True), P(c((-5, -2), (5, 2))), P(c((-5, 2), (5, -2))), P(c((-2.2, -2), (-2.2, 2))), P(c((2.2, -2), (2.2, 2)))]
                                           + [P(c((x, 2), (x, 3.3))) for x in (-4.5, 4.5)] + [P(c((x, -2), (x, -3.3))) for x in (-4.5, 4.5)],
                                           basis=basis('3.6', '2516', 15, False, '接口位置按页面目测'))

# ------------------------------------------------------------------ 容器与塔（第 1、2 组）
_D['ISO Vertical Vessel Style'] = dict(zh='立式容器（椭圆封头）', cat='容器与储罐', use='立式容器，椭圆封头；顶/底中心及左右侧接口', block=True,
                                      ports={'top': (0, 7 * C), 'bottom': (0, -7 * C), 'left_upper': (-4 * C, 3 * C), 'right_lower': (4 * C, -3 * C), 'left_lower': (-4 * C, -3 * C), 'right_upper': (4 * C, 3 * C)},
                                      paths=_vessel_v(4, 7, 1.5), basis=basis('1.5', '2062', 7, True, '宽高比按页面取 8:14'))
_D['ISO Horizontal Vessel Style'] = dict(zh='卧式容器（椭圆封头）', cat='容器与储罐', use='卧式容器，椭圆封头；左右端及顶/底接口', block=True,
                                        ports={'left': (-7 * C, 0), 'right': (7 * C, 0), 'top_left': (-3 * C, 4 * C), 'top_right': (3 * C, 4 * C), 'bottom': (0, -4 * C)},
                                        paths=_vessel_h(7, 4, 1.5), basis=basis('1.5', '2062', 7, True, '页面为立式，横置后使用'))
_D['ISO Tray Column Style'] = dict(zh='板式塔', cat='容器与储罐', use='板式塔（通用，虚线塔板）', block=True,
                                  ports={'top': (0, 11 * C), 'bottom': (0, -11 * C), 'left_upper': (-2.5 * C, 7 * C), 'right_lower': (2.5 * C, -7 * C)},
                                  paths=_vessel_v(2.5, 11, 1.2) + [P(c((-2.5, y), (-1.5, y))) for y in (6, 0, -6)] + [P(c((-0.5, y), (0.5, y))) for y in (6, 0, -6)] + [P(c((1.5, y), (2.5, y))) for y in (6, 0, -6)],
                                  basis=basis('2.2', 'X8101', 13, True, '塔板数量由版面决定，此处示意 3 层'))
_D['ISO Fixed Bed Column Style'] = dict(zh='固定床塔/反应器', cat='容器与储罐', use='固定床塔（X 填料层）', block=True,
                                       ports={'top': (0, 8 * C), 'bottom': (0, -8 * C), 'left_upper': (-3 * C, 5 * C), 'right_lower': (3 * C, -5 * C)},
                                       paths=_vessel_v(3, 8, 1.3) + [P(c((-3, 3), (3, 3))), P(c((-3, -3), (3, -3))), P(c((-3, 3), (3, -3))), P(c((-3, -3), (3, 3)))], basis=basis('2.4', 'X8015', 13, True))


def check():
    n = ok = 0
    for k, d in ISO_DEFS.items():
        n += 1
        ok += bool(d['basis']['verified'])
        print(('核对' if d['basis']['verified'] else '待核'), k, d['basis']['item'], d['basis']['reg'], 'PDF', d['basis']['pdf_page'])
    print(n, '个符号，已逐个目测核对', ok)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        check()
