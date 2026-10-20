"""已验证的版面模块（声明式）。代理只说明“用哪种支路、有哪些元件、接到哪里”，常规间距、标注位置、线上对象和三通连接由这里生成，
不用每个项目再逐个设备写坐标（日常 token 主要花在这类重复坐标和布局返工上）。
用法（版面模块里）:
    from pidlib import *
    from patterns import gas_branch, route, control_loop
    gas_branch(s, y=268, fluid='H2', num='0101', bl='BL-H2', label='H₂ 气源', hv='HV-101', fl='FL-101', pcv='PCV-101',
               pi='PI-101', xv='XV-101', mfc='FIC-101', ck='CK-101', x_end=360)
模块只做版面，不决定要不要某个元件：安全保护元件的有无与规格由模型（项目设计）决定，参数写 None 即不画。
"""
import pidlib
from pidlib import attach, ib, oval

# 元件沿线的默认 x（mm，A3；青木子项目实测可用，并行支路间距 26 mm 时标注不互碰）
X = dict(bl=40, hv=64, fl=88, tin=100, pcv=114, pi=128, tbp1=140, xv=154, mfc=192, tbp2=216, ck=232)


def gas_branch(s, y, fluid, num, *, bl=None, label=None, hv=None, fl=None, pcv=None, pi=None, xv=None, mfc=None, ck=None,
               x_end, x=None, anno_x=285, size='6', spec='S1', tap_id=None):
    """气源处理支路：界区旗 → 手阀 → 过滤器 → 减压阀（+就地压力表取压）→ 切断阀 → 流量控制器 → 止回阀 → 集管。
    线号 = {fluid}-{num}-{size}-{spec}；线 id = L{fluid}。tap_id 是压力表取压短线的 id（缺省 LP{压力表位号}）。
    x 可覆盖默认列位；返回 {'line': 线 id, 'no': 线号, 'x': 列位字典, 'y': y}，供旁路、取气口按列位接入。"""
    xs = dict(X, **(x or {}))
    ln = f'{fluid}-{num}-{size}-{spec}'
    L = f'L{fluid}'
    s.line(L, [[xs['bl'] + 10, y], [x_end, y]], ln, anno=[anno_x, y])
    if bl:
        s.tie(bl, [xs['bl'], y], L, 'start', label=label, label_at=[xs['bl'] - 10, y + 6.5] if label else None)
    if hv:
        s.hand(hv, [xs['hv'], y], L, anno=oval(xs['hv'], y - 11))
    if fl:
        s.special(fl, [xs['fl'], y], L, anno=oval(xs['fl'], y - 11))
    if pcv:
        s.pcv(pcv, [xs['pcv'], y], L, anno=ib(xs['pcv'] - 2, y + 15))
    if pi:
        tap = tap_id or f'LP{pi}'
        s.bubble(pi, [xs['pi'], y + 14])
        s.line(tap, [[xs['pi'], y], [xs['pi'], y + 9]], ln, style='Secondary Style')
        s.tee(tap, L, True)
        s.items.append({'k': 'connect', 'line': tap, 'asset': pi, 'ctx': 'end'})
    if xv:
        s.xv(xv, [xs['xv'], y], L, anno=ib(xs['xv'], y + 15), fail_text_at=[xs['xv'] - 7, y + 6])
    if mfc:
        s.inst_inline(mfc, [xs['mfc'], y], L, anno=ib(xs['mfc'], y + 14))
    if ck:
        s.hand(ck, [xs['ck'], y], L, anno=oval(xs['ck'], y - 11))
    return {'line': L, 'no': ln, 'x': xs, 'y': y}


def route(a, b, first='h'):
    """两点之间的正交折线（先横后竖 first='h'，先竖后横 first='v'）；共线时只返回两点。"""
    a, b = list(a), list(b)
    if abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6:
        return [a, b]
    mid = [b[0], a[1]] if first == 'h' else [a[0], b[1]]
    return [a, mid, b]


from pidlib import KIND_STYLE  # noqa: E402


def _find(s, tag):
    for it in s.items:
        if it.get('id') == tag and it['k'] in ('asset', 'cv'):
            return it
    raise KeyError(f'{s.no} 上还没有 {tag}：先画对象，再画回路')


def control_loop(s, loop, measure, controller, final, *, kind_in='electric', kind_out='electric', side_in=('R', 'L'),
                 side_out=('R', 'L'), first='h'):
    """控制回路的信号：测量 → 控制功能 → 最终元件。三者须已画在本图上（measure/controller/final 为位号）。
    信号线型由 kind 决定（electric / pneumatic / data），不因“都经过 PLC”而统一；线 id = S{loop}a / S{loop}b。
    side_*：(起点侧, 终点侧)，取 attach 的 'L' 'R' 'T' 'B'。返回两条信号线 id。"""
    def port(tag, side):
        it = _find(s, tag)
        st = it.get('style') or it.get('body')
        try:
            return attach(st, it['at'], side, it.get('rot', 0), it.get('scale'))
        except ValueError:          # 目录里没有连接点的符号（MFC、设备）：取外框该侧中点
            import geometry
            x0, y0, x1, y1 = geometry.item_box(pidlib.CATALOG, it)
            return {'L': [x0, (y0 + y1) / 2], 'R': [x1, (y0 + y1) / 2], 'B': [(x0 + x1) / 2, y0], 'T': [(x0 + x1) / 2, y1]}[side]
    ids = []
    for suffix, (a, b), kind, sides in (('a', (measure, controller), kind_in, side_in), ('b', (controller, final), kind_out, side_out)):
        lid = f'S{loop}{suffix}'
        s.sigc(lid, route(port(a, sides[0]), port(b, sides[1]), first), KIND_STYLE[kind], a, b)
        ids.append(lid)
    return ids
