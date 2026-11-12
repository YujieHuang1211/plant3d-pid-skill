"""ISA-5.1-2024 与 ISO 1219 风格的符号定义（自绘几何，按原件页面的形状；不含标准的图形文件或页面截图）。
与 iso_symbols.py 相同的约定：插入点在符号中心，ports 是连接点（相对插入点，mm），block=True 画成一个块参照。
依据（已对原件逐个目测）：
  ISA-5.1-2024 表11第9项 隔膜阀（PDF 第45页，印刷页44）；表12第1项 弹簧薄膜执行机构（PDF 第47页，印刷页46）。
  ISO 1219-1 气动符号：直动/先导电磁阀弹簧复位 3/2 常闭、先导电磁阀 5/2（公开讲义《SIMBOLOGIA PNEUMATICA ISO 1219-1》第128–131页）。
命令行：python symbol_geom.py build-native 后生效。
"""
import math

from iso_symbols import P


def _arc_pts(cx, cy, r, a0, a1, n=20):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _arrow(x0, y0, x1, y1, head=0.9):
    """线段加实心三角箭头（箭头在 x1,y1 端）"""
    a = math.atan2(y1 - y0, x1 - x0)
    bx, by = x1 - head * 1.6 * math.cos(a), y1 - head * 1.6 * math.sin(a)
    px, py = -math.sin(a) * head * 0.6, math.cos(a) * head * 0.6
    return [P([(x0, y0), (bx, by)]), P([(x1, y1), (bx + px, by + py), (bx - px, by - py)], True, True)]


def _block(x, y):
    """气动阀的“闭”：从口线向内画一条短线加横杠（⊤）；x,y 为端口处（在方格边上），短线向 -y 方向（口在下）或 +y 方向由符号 up 决定"""
    pass


def _tee_stop(x, y_port, y_in, bar=0.6):
    """闭端：口线 (x,y_port) → (x,y_in)，再在 y_in 处画横杠"""
    return [P([(x, y_port), (x, y_in)]), P([(x - bar, y_in), (x + bar, y_in)])]


def _spring(x0, x1, y, n=4, amp=1.1):
    pts = [(x0, y)]
    step = (x1 - x0) / (n * 2)
    for i in range(1, n * 2):
        pts.append((x0 + step * i, y + (amp if i % 2 else -amp)))
    pts.append((x1, y))
    return P(pts)


def _solenoid(x0, x1, h=2.5):
    """电磁操作器：方框加斜线"""
    return [P(_rect(x0, -h, x1, h), True), P([(x0 + 0.5, -h + 0.7), (x1 - 0.5, h - 0.7)])]


def _pilot(x0, x1, h=2.5):
    """先导操作：方框内向右的空心三角（指向阀体）"""
    return [P(_rect(x0, -h, x1, h), True), P([(x0 + 0.8, -1.4), (x1 - 0.8, 0), (x0 + 0.8, 1.4), (x0 + 0.8, -1.4)], True)]


def _isa_pneumatic_diaphragm():
    paths = [P(_rect(-4, -2, 4, 2), True),
             P(_arc_pts(0, 6.4, 5.5, 235, 305)[:], False),                     # 下凹圆弧（隔膜），弧底约 y=0.9
             P([(-0.7, -2), (0.7, -2), (0, -0.5), (-0.7, -2)], True, True),    # 隔膜下方实心小三角
             P([(0, 2), (0, 6.0)]),                                              # 阀杆
             P(_arc_pts(0, 6.0, 2.6, 0, 180) + [(2.6, 6.0)], False),             # 弹簧薄膜执行机构：圆顶
             ]
    return paths


def _isa_diaphragm_body():
    return [P(_rect(-4, -2, 4, 2), True),
            P(_arc_pts(0, 6.4, 5.5, 235, 305)[:], False),
            P([(-0.7, -2), (0.7, -2), (0, -0.5), (-0.7, -2)], True, True)]


def _isa_piston_globe():
    """气动活塞式截止阀（角座阀）：ISO 10628-2 截止阀阀体（21.4）加 ISA-5.1 表12第4项线性活塞执行机构（方框，单作用弹簧对置或双作用）。
    角座阀是直通式 Y 型座阀，管线不转向，所以阀体用直通截止阀，不用转角的角阀（21.5）。"""
    from iso_symbols import ISO_DEFS
    body = [dict(x) for x in ISO_DEFS['ISO Globe Valve Style']['paths']]
    return body + [P([(0, 0.35), (0, 3.6)]), P(_rect(-2.6, 3.6, 2.6, 7.8), True)]


def _isa_piston_ball():
    """气动球阀：ISO 10628-2 球阀阀体（21.7）加 ISA-5.1 表12第6项旋转活塞执行机构（三格方框，单作用弹簧对置或双作用）。"""
    from iso_symbols import ISO_DEFS
    body = [dict(x) for x in ISO_DEFS['ISO Ball Valve Style']['paths']]
    return body + [P([(0, 0.5), (0, 3.6)]), P(_rect(-4.5, 3.6, 4.5, 7.4), True), P([(-1.5, 3.6), (-1.5, 7.4)]), P([(1.5, 3.6), (1.5, 7.4)])]


def _isa_rotameter_needle():
    """转子流量计带针阀：ISA-5.1-2009 表 5.4.3 的 b 方案（竖矩形内画上宽下窄的小梯形，表示锥管和浮子位置），
    矩形宽 3u、高 6u，梯形上边 1.5u、下边 0.75u、高 1.5u、距矩形顶 2u（u=1.5 mm）；针阀（ISO 10628-2 针阀符号：蝴蝶结加实心小三角）串在进口侧。
    进口在左，出口在右，口线落在蝴蝶结两端和矩形左右边的中点。"""
    u = 1.5
    x0 = -7.25                                   # 针阀左端（进口）
    vx = x0 + 3.0                                # 蝴蝶结中心
    rx0, rx1 = 2.75, 2.75 + 3 * u                # 矩形左右边
    cx = (rx0 + rx1) / 2
    top = 3 * u
    t_top = top - 2 * u
    p = [P([(x0, 1.6), (vx, 0), (x0, -1.6), (x0, 1.6)], True), P([(vx + 3.0, 1.6), (vx, 0), (vx + 3.0, -1.6), (vx + 3.0, 1.6)], True),
         P([(vx, -0.2), (vx - 0.7, -3.0), (vx + 0.7, -3.0), (vx, -0.2)], True, True),
         P([(vx + 3.0, 0), (rx0, 0)]),
         P(_rect(rx0, -top, rx1, top), True),
         P([(cx - 0.75 * u, t_top), (cx + 0.75 * u, t_top), (cx + 0.375 * u, t_top - 1.5 * u), (cx - 0.375 * u, t_top - 1.5 * u), (cx - 0.75 * u, t_top)], True)]
    return p


def _v32():
    """ISO 1219 先导电磁式 3/2 常闭阀，弹簧复位。两格 5×5：左格＝得电位（1→2 连通，3 封闭），右格＝常态位（1 封闭，2→3 排气）；
    口在右格上：2 在上（x=3.75），1 在下右（x=3.75），3 在下左（x=1.25）。操作器在左，弹簧在右。"""
    h = 2.5
    p = []
    p += [P(_rect(-5, -h, 0, h), True), P(_rect(0, -h, 5, h), True)]
    # 左格：1→2 竖直箭头（x=-1.25），3 封闭（x=-3.75，⊤）
    p += _arrow(-1.25, -h, -1.25, h)
    p += _tee_stop(-3.75, -h, -1.0)
    # 右格：2→3 斜箭头（自 (3.75,h) 到 (1.25,-h)），1 封闭（x=3.75）
    p += _arrow(3.75, h, 1.25, -h)
    p += _tee_stop(3.75, -h, -1.0)
    # 操作器：电磁线圈、先导，弹簧
    p += _solenoid(-12.5, -9.0, h)
    p += _pilot(-9.0, -5.0, h)
    p += [_spring(5, 9.5, 0)]
    # 口线
    p += [P([(3.75, h), (3.75, 5.0)]), P([(3.75, -h), (3.75, -5.0)]), P([(1.25, -h), (1.25, -5.0)])]
    return p


def _v52():
    """ISO 1219 双电控 5/2 阀（两端电磁，无弹簧）。两格 6×6，口画在右格：上 4（x=2）、2（x=4）；下 5（x=1）、1（x=3）、3（x=5）。
    右格（口所在位）：1→2、4→5；左格：1→4、2→3。"""
    h = 3.0
    p = [P(_rect(-6, -h, 0, h), True), P(_rect(0, -h, 6, h), True)]
    p += _arrow(3.0, -h, 4.0, h)        # 右格 1→2
    p += _arrow(2.0, h, 1.0, -h)        # 右格 4→5
    p += _arrow(-3.0, -h, -4.0, h)      # 左格 1→4（右格坐标 3→2 左移 6）
    p += _arrow(-2.0, h, -1.0, -h)      # 左格 2→3（右格 4→5 的位置 → 2→3: 4→5 的端口为 2 到 3: top x=4-6=-2, bottom x=5-6=-1）
    p += _solenoid(-11.5, -6.0, h)
    p += _solenoid(6.0, 11.5, h)
    for x in (2.0, 4.0):
        p.append(P([(x, h), (x, 5.5)]))
    for x in (1.0, 3.0, 5.0):
        p.append(P([(x, -h), (x, -5.5)]))
    return p


def _basis(std, item, pdf, note=''):
    return {'std': std, 'item': item, 'pdf_page': pdf, 'verified': True, 'note': note}


ISA = 'ANSI/ISA-5.1-2024'
I1219 = 'ISO 1219-1（公开讲义 SIMBOLOGIA PNEUMATICA ISO 1219-1）'

DEFS_R3 = {
    'ISA Diaphragm Valve Style': dict(zh='隔膜阀（阀体）', cat='手动阀', use='隔膜阀阀体：矩形加下凹圆弧和实心小三角（ISA-5.1 表11第9项a）', block=True,
                                      ports={'in': (-4, 0), 'out': (4, 0)}, paths=_isa_diaphragm_body(),
                                      basis=_basis(ISA, '表11 第9项a', 45, '阀体；需要执行机构时用 ISA Pneumatic Diaphragm Valve Style')),
    'ISA Pneumatic Diaphragm Valve Style': dict(zh='气动隔膜阀（弹簧薄膜执行机构）', cat='调节阀与执行机构',
                                                use='气动隔膜阀：隔膜阀阀体加弹簧薄膜执行机构（圆顶）；气动信号接圆顶顶部；失效位置在符号旁标 FC 或 FO',
                                                block=True, ports={'in': (-4, 0), 'sig': (0, 8.6), 'out': (4, 0)}, paths=_isa_pneumatic_diaphragm(),
                                                basis=_basis(ISA, '表11 第9项a + 表12 第1项', 45, '执行机构圆顶压在阀杆上；气动信号线由圆顶顶部接入')),
    'ISA Pneumatic Piston Globe Valve Style': dict(zh='气动角座阀（线性活塞执行机构）', cat='调节阀与执行机构',
                                                   use='气动角座阀（直通式 Y 型活塞阀）：截止阀阀体加线性活塞执行机构方框；气动信号接方框顶部；失效位置在符号旁标 FC 或 FO',
                                                   block=True, ports={'in': (-4, 0), 'sig': (0, 7.8), 'out': (4, 0)}, paths=_isa_piston_globe(),
                                                   basis=_basis(ISA, '表12 第4项（线性活塞执行机构）+ ISO 10628-2 表2 第21.4（截止阀）', 47, '阀体按 ISO 截止阀，执行机构按 ISA-5.1 线性活塞，单作用弹簧对置或双作用不加区分，失效位置另行标注')),
    'ISA Pneumatic Piston Ball Valve Style': dict(zh='气动球阀（旋转活塞执行机构）', cat='调节阀与执行机构',
                                                  use='气动球阀：球阀阀体加旋转活塞执行机构三格方框；气动信号接方框顶部；失效位置在符号旁标 FC 或 FO',
                                                  block=True, ports={'in': (-4, 0), 'sig': (0, 7.4), 'out': (4, 0)}, paths=_isa_piston_ball(),
                                                  basis=_basis(ISA, '表12 第6项（旋转活塞执行机构）+ ISO 10628-2 表2 第21.7（球阀）', 47, '单作用弹簧对置或双作用不加区分，失效位置另行标注')),
    'ISA Rotameter Needle Valve Style': dict(zh='转子流量计带针阀（ISA-5.1 表 5.4.3 b 方案）', cat='流量与测量元件',
                                             use='转子流量计：竖矩形内画上宽下窄小梯形，进口侧串针阀；左进右出；位号 FI', block=True,
                                             ports={'in': (-7.25, 0), 'out': (7.25, 0)}, paths=_isa_rotameter_needle(),
                                             basis=_basis(ISA + '（2009 版转载页对照）', '表 5.4.3 方案 b + ISO 10628-2 针阀', 0, '尺寸按 2009 版比例，现行 2024 版尺寸未逐项核对；u=1.5 mm')),
    'ISO1219 3-2 Pilot Solenoid NC Style': dict(zh='3/2 先导电磁阀（常闭，弹簧复位）', cat='调节阀与执行机构',
                                                use='阀岛里的先导电磁阀：口 2（A）在上，口 1（P）下右，口 3（R）下左', block=True,
                                                ports={'A': (3.75, 5.0), 'P': (3.75, -5.0), 'R': (1.25, -5.0)}, paths=_v32(),
                                                basis=_basis(I1219, '先导电磁式 3/2 常闭、弹簧复位', 129)),
    'ISO1219 5-2 Double Solenoid Style': dict(zh='5/2 双电控换向阀', cat='调节阀与执行机构',
                                              use='下压气缸换向阀：口 4、2 在上，口 5、1、3 在下', block=True,
                                              ports={'4': (2.0, 5.5), '2': (4.0, 5.5), '5': (1.0, -5.5), '1': (3.0, -5.5), '3': (5.0, -5.5)}, paths=_v52(),
                                              basis=_basis(I1219, '电磁式 5/2（两端电磁操作）', 130, '口位按讲义第130页的 5/2 图')),
}
