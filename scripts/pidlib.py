"""P&ID 版面库：由 pid_model.json + 每张图的版面坐标生成 PidBot 绘图 spec（JSON）。
项目里的版面模块这样用：

    from pidlib import *            # Sheet、use_model、oval、ib、wrap、table、CN、SMALL …
    use_model('pid_model.json')     # 绑定项目模型（设备/在线件/仪表/界区/联锁/工况/图纸清单）

    def sheet_101():
        s = Sheet('P&ID-101')
        s.line('LH2', [[50, 268], [360, 268]], 'H2-0101-6-S1', anno=[285, 268])
        s.hand('HV-101', [64, 268], 'LH2', anno=oval(64, 257))
        ...
        return s

坐标单位 mm，模型空间 = A3 图纸坐标：可绘区 x 25–415、y 5–292；右下 x>235、y<91 为标题栏+修订栏禁区。
连接点、符号外框见 assets/symbol_catalog.json；用 attach() 取实测连接点，避免线端差 1 mm 而“看似未连上”。
"""
import json
from pathlib import Path

CN = 3.5      # 汉字字高（GB/T 14691 最小 3.5）
SMALL = 2.5   # 数字/字母字高
H = 3.5       # 表格字高
ROWH = 5.6    # 表格每行高度

M = {}
INL, INS, EQP, BND, IL = {}, {}, {}, {}, {}
PROPS_DEFAULT = {'Area': '—', 'Author': '—', 'Revision': 'A', 'Stage': '方案设计', 'Scale': 'NTS',
                 'Checker': '—', 'Reviewer': '—', 'Approver': '—', 'RevNote': '首版，供审查'}
CATALOG = {}

STYLE = {
    'ball_valve': 'Ball Valve Style', 'needle_valve': 'Needle Valve Style', 'check_valve': 'Check Valve Style',
    'filter': 'Filter Pipe Style', 'mfc': 'QMZ MFC Style', 'flow_switch': 'QMZ Flow Switch Style', 'cap': 'Cap Style',
}


def use_model(model, catalog=None, **props_default):
    """绑定项目模型（路径或已读入的 dict）；props_default 覆盖标题栏默认值（如 Stage='施工图设计'）。"""
    global M
    M.clear()
    M.update(json.loads(Path(model).read_text(encoding='utf-8')) if not isinstance(model, dict) else model)
    INL.clear(); INL.update({x['tag']: x for x in M.get('inline', [])})
    INS.clear(); INS.update({x['tag']: x for x in M.get('instruments', [])})
    EQP.clear(); EQP.update({x['tag']: x for x in M.get('equipment', [])})
    BND.clear(); BND.update({x['id']: x for x in M.get('boundary', [])})
    IL.clear(); IL.update({x['id']: x for x in M.get('interlocks', [])})
    PROPS_DEFAULT.update(props_default)
    cat = Path(catalog) if catalog else Path(__file__).resolve().parent.parent / 'assets' / 'symbol_catalog.json'
    CATALOG.clear()
    if cat.exists():
        CATALOG.update(json.loads(cat.read_text(encoding='utf-8')))
    return M


def shx(t):
    """SHX 字体（gbenor/gbcbig）无下标字符与 en dash：改用 MText 堆叠与 ~"""
    for a, b in (('₂', r'\S^2;'), ('₄', r'\S^4;'), ('²', r'\S2^;'), ('–', '~'), ('Ø', '%%c')):
        t = t.replace(a, b)
    return t


def split_tag(tag):
    a, b = tag.split('-', 1)
    return a, b


def attach(style, at, side, rot=0):
    """符号实测连接点（世界坐标）。side：'L' 'R' 'T' 'B' 取最左/右/上/下的连接点，或整数下标。
    仪表圈、联锁菱形：中心 ±5 mm 四个顶点；阀门：插入点 ±4 mm 两端。目录无此样式时抛 KeyError。"""
    import math
    c = CATALOG[style]
    pts = []
    for dx, dy in c['att']:
        a = math.radians(rot)
        pts.append((round(at[0] + dx * math.cos(a) - dy * math.sin(a), 2), round(at[1] + dx * math.sin(a) + dy * math.cos(a), 2)))
    if isinstance(side, int):
        return list(pts[side])
    key = {'L': lambda p: p[0], 'R': lambda p: -p[0], 'B': lambda p: p[1], 'T': lambda p: -p[1]}[side]
    return list(min(pts, key=key))


class Sheet:
    OPC_LEN = 42.19   # Off Page Connector Style 长度（1.6875×25）

    def __init__(self, no):
        self.no = no
        self.items = []

    # ------------------------------------------------------------ 基本对象
    def text(self, x, y, s, h=CN, just='ML', **kw):
        self.items.append({'k': 'text', 'at': [x, y], 'text': shx(s), 'h': h, 'just': just, 'layer': '注释', **kw})

    def line(self, lid, pts, no, style='Primary Style', anno=None):
        fluid, num, size, spec = no.split('-')
        it = {'k': 'line', 'id': lid, 'style': style, 'pts': pts,
              'group': {'Service': fluid, 'LineNumber': num, 'NominalSize': size, 'NominalSpec': spec},
              'props': {'Size': size, 'Spec': spec}}
        if anno:
            it['anno'] = anno
        self.items.append(it)

    def sig(self, lid, pts, style='Electrical Style'):
        self.items.append({'k': 'line', 'id': lid, 'style': style, 'pts': pts})

    def props_common(self, tag, src_rec):
        p = {'Description': src_rec.get('desc', src_rec.get('name', ''))[:120]}
        if src_rec.get('spec'):
            p['Comment'] = src_rec['spec'][:250]
        src = src_rec.get('src', '')
        p['BasisRef'] = src[:120]
        p['BasisCategory'] = '设计确认' if ('U' in src.split('/')[0] or '设计确认' in src) else ('甲方输入' if src.startswith('C') else '设计依据/工程假设')
        return p

    def hand(self, tag, at, line, anno=None, rot=0):
        rec = INL[tag]
        code, num = split_tag(tag)
        p = {'Code': code, 'Number': num, **self.props_common(tag, rec)}
        style = STYLE[rec['type']]
        if rec.get('normally') == 'NC':          # 常关手动阀：PIP 填黑符号
            style = {'Ball Valve Style': 'Ball Valve Closed Style', 'Needle Valve Style': 'Needle Valve Closed Style'}.get(style, style)
            p['Normally'] = 'NC'
        self.items.append({'k': 'asset', 'id': tag, 'style': style, 'at': at, 'rot': rot, 'props': p,
                           **({'anno': anno} if anno else {})})
        self.items.append({'k': 'connect', 'line': line, 'asset': tag, 'ctx': 'inline'})

    def special(self, tag, at, line, anno=None):
        rec = INL[tag]
        typ, num = split_tag(tag)
        p = {'Type': typ, 'Number': num, **self.props_common(tag, rec)}
        self.items.append({'k': 'asset', 'id': tag, 'style': STYLE[rec['type']], 'at': at, 'props': p, **({'anno': anno} if anno else {})})
        self.items.append({'k': 'connect', 'line': line, 'asset': tag, 'ctx': 'inline'})

    def inst_inline(self, tag, at, line, anno=None):
        rec = INL[tag]
        typ, loop = split_tag(tag)
        ins = INS.get(tag, {})
        p = {'Type': typ, 'LoopNumber': loop, **self.props_common(tag, rec)}
        if ins.get('io'):
            p['IOPoint'] = ins['io']
        if ins.get('setpoint'):
            p['AlarmTripSetting'] = ins['setpoint']
        self.items.append({'k': 'asset', 'id': tag, 'style': STYLE[rec['type']], 'at': at, 'props': p, **({'anno': anno} if anno else {})})
        self.items.append({'k': 'connect', 'line': line, 'asset': tag, 'ctx': 'inline'})

    def xv(self, tag, at, line, anno, fail_text_at, below=False):
        rec = INL[tag]
        typ, loop = split_tag(tag)
        ins = INS.get('XY-' + loop, {})
        p = {'Type': typ, 'LoopNumber': loop, 'FailSafePosition': rec.get('fail', ''), 'IOPoint': ins.get('io', ''), **self.props_common(tag, rec)}
        self.items.append({'k': 'cv', 'id': tag, 'body': 'Diaphragm Valve Style', 'act': 'QMZ Diaphragm Solenoid Actuator',
                           'at': at, 'rot': 0, 'props': p, 'anno': anno})
        self.items.append({'k': 'connect', 'line': line, 'asset': tag, 'ctx': 'inline'})
        self.text(fail_text_at[0], fail_text_at[1], rec.get('fail', ''), SMALL, 'MC')

    def pcv(self, tag, at, line, anno):
        rec = INL[tag]
        typ, loop = split_tag(tag)
        p = {'Type': typ, 'LoopNumber': loop, **self.props_common(tag, rec)}
        self.items.append({'k': 'cv', 'id': tag, 'body': 'Globe Valve Style', 'act': 'PressureReducingRegulator Style',
                           'at': at, 'props': p, 'anno': anno})
        self.items.append({'k': 'connect', 'line': line, 'asset': tag, 'ctx': 'inline'})

    def bubble(self, tag, at, style='Field Mounted Discrete Instrument Style', cls_extra=None):
        rec = INS[tag]
        typ, loop = split_tag(tag)
        p = {'Type': typ, 'LoopNumber': loop, **self.props_common(tag, rec)}
        if rec.get('range'):
            p['InstrRange'] = rec['range']
        if rec.get('setpoint'):
            p['AlarmTripSetting'] = rec['setpoint']
        if rec.get('io'):
            p['IOPoint'] = rec['io']
        self.items.append({'k': 'asset', 'id': tag, 'style': style, 'at': at, 'props': p, 'auto': True})   # 不在线上：开自动化以填位号属性

    def tie(self, bid, at, line, ctx, rot=0, label=None, label_at=None):
        rec = BND[bid]
        num = '{:03d}'.format(list(BND).index(bid) + 1)
        p = {'Type': 'TP', 'Number': num, 'Description': rec['desc'], 'Comment': rec['cond'], 'Supplier': rec['by'], 'BasisRef': rec['src']}
        self.items.append({'k': 'asset', 'id': bid, 'style': 'QMZ Battery Limit Style', 'at': at, 'rot': rot, 'props': p})
        self.items.append({'k': 'connect', 'line': line, 'asset': bid, 'ctx': ctx})
        if label:
            self.text(label_at[0], label_at[1], label, CN, 'ML')

    def opc(self, oid, at, line, ctx, dest, number, rot=0):
        """出口（ctx=end）：连接器插入点=管线终点，箭头沿流向。
        进口（ctx=start）：Plant 要求连接器方向与管线流向一致，连接器放在管线起点上游、箭头尖=管线起点。
        rot=180 的进口（管线向右流）自动换算为 rot=0、插入点左移一个连接器长度。"""
        if ctx == 'start':
            ang = 0 if rot in (0, 180) else rot
            dx = {0: -self.OPC_LEN, 90: 0, 270: 0}.get(ang, -self.OPC_LEN)
            dy = {90: -self.OPC_LEN, 270: self.OPC_LEN}.get(ang, 0)
            at, rot = [at[0] + dx, at[1] + dy], ang
        self.items.append({'k': 'asset', 'id': oid, 'style': 'Off Page Connector Style', 'at': at, 'rot': rot,
                           'props': {'ConnectorNumber': number, 'OriginOrDestination': dest}, 'auto': True})   # 关闭自动化时连接器文字不绑定属性
        self.items.append({'k': 'connect', 'line': line, 'asset': oid, 'ctx': ctx})


    # ------------------------------------------------------------ 设备、管嘴、PLC 功能、联锁、信号线、跨图配对
    def equip(self, tag, style, at, anno=None, rot=0):
        rec = EQP[tag]
        typ, num = split_tag(tag)
        p = {'Type': typ, 'Number': num, 'Description': rec['name'], 'Comment': rec['spec'][:250],
             'Supplier': rec['by'], 'BasisRef': rec['src']}
        it = {'k': 'asset', 'id': tag, 'style': style, 'at': at, 'rot': rot, 'props': p, 'auto': True}
        if anno:
            it['anno'] = {'at': anno, 'style': 'Equipment Tag'}
        self.items.append(it)

    def nozzle(self, owner, nid, at, rot=0):
        self.items.append({'k': 'nozzle', 'id': nid, 'on': owner, 'style': 'Assumed Nozzle Style', 'at': at, 'rot': rot})

    def connect(self, line, asset, ctx):
        self.items.append({'k': 'connect', 'line': line, 'asset': asset, 'ctx': ctx})

    def plc(self, tag, at, desc=None):
        rec = INS.get(tag, {'desc': desc or tag, 'src': 'R1 控制点位'})
        typ, loop = split_tag(tag)
        p = {'Type': typ, 'LoopNumber': loop, **self.props_common(tag, rec)}
        for k, f in (('range', 'InstrRange'), ('setpoint', 'AlarmTripSetting'), ('io', 'IOPoint')):
            if rec.get(k):
                p[f] = rec[k]
        self.items.append({'k': 'asset', 'id': tag, 'style': 'Primary Loc Accessible PLC Style', 'at': at, 'props': p, 'auto': True})

    def ilock(self, iid, at, hardware=False):
        rec = {x['id']: x for x in M['interlocks']}[iid]
        p = {'Type': 'I', 'LoopNumber': iid.split('-')[1], 'Description': rec['cause'][:120],
             'AlarmTripSetting': rec['setpoint'], 'BasisRef': rec['src'][:120],
             'Comment': '；'.join(f'{k}:{v}' for k, v in rec['actions'].items())[:250]}
        # 软件联锁在 PLC 中执行：ISA-5.1 PLC 逻辑符号（方框内菱形），PIP 的 Undefined Interlock Logic 为无位号类，不用
        st = 'Field Mounted Discrete Hardware Interlock Style' if hardware else 'Primary Loc Accessible PLC Style'
        self.items.append({'k': 'asset', 'id': iid, 'style': st, 'at': at, 'props': p, 'auto': True})

    def sigc(self, lid, pts, style, a=None, b=None):
        self.items.append({'k': 'line', 'id': lid, 'style': style, 'pts': pts})
        if a:
            self.connect(lid, a, 'start')
        if b:
            self.connect(lid, b, 'end')

    def pair(self, a, b):
        self.items.append({'k': 'opc', 'a': a, 'b': b})

    def tee(self, line, to, start):
        self.items.append({'k': 'tee', 'line': line, 'to': to, 'start': start})

    def dump(self, out):
        p = Path(out) / f'{self.no}.json'
        p.write_text(json.dumps({'clear': False, 'items': self.items}, ensure_ascii=False, indent=1), encoding='utf-8')
        # 图纸属性（驱动标题栏字段）
        sh = {x['no']: x for x in M['sheets']}[self.no]
        order = [x['no'] for x in M['sheets']]
        d = PROPS_DEFAULT
        props = {'PnID': self.no, 'Title': sh['title'], 'Description': sh.get('content', sh['title']),
                 'Area': d['Area'], 'Author': d['Author'], 'Revision': d['Revision'], 'Stage': d['Stage'], 'Scale': d['Scale'],
                 'SheetNo': str(order.index(self.no) + 1), 'SheetTotal': str(len(order)),
                 'Checker': d['Checker'], 'Reviewer': d['Reviewer'], 'Approver': d['Approver'],
                 'IssueDate': M['meta']['date'], 'RevNote': d['RevNote']}
        props = {k: v.replace('₂', '2').replace('₄', '4').replace('–', '~') for k, v in props.items()}   # 字段值不解释 MText 代码
        (Path(out) / f'{self.no}.props.json').write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding='utf-8')
        return p


# ================================================================ 标注位置（实测）：仪表圈中心=给定点；椭圆位号框中心=给定点
def oval(x, y):
    """椭圆位号框（Oval Tag Style）中心 = 给定点"""
    return {'at': [x, y], 'style': 'Oval Tag Style'}


def ib(x, y):
    """ISA 现场仪表圈（Field Mounted Discrete Instrument Style）中心 = 给定点；不指定会取到 DCS 共享显示样式"""
    return {'at': [x, y], 'style': 'Field Mounted Discrete Instrument Style'}


# ================================================================ 表格与折行（封面目录、图例、联锁/工况表）
def _cw(ch, h):
    return h if ord(ch) > 0x2E80 else h * 0.62


def wrap(t, width, h=H):
    """按列宽折行：汉字宽≈字高，西文≈0.6 字高（偏保守）；西文单词不从中间断开（优先在空格、/、、处断）"""
    out, line, w = [], '', 0.0
    for ch in str(t):
        cw = _cw(ch, h)
        if ch == '\n' or w + cw > width - 2.4:
            if ch == '\n':
                out.append(line)
                line, w = '', 0.0
                continue
            cut = -1
            if ord(ch) < 0x2E80 and line and ord(line[-1]) < 0x2E80:          # 正在一个西文词中间
                cut = max(line.rfind(' '), line.rfind('/'), line.rfind('、'), line.rfind('，'))
                if cut < len(line) - 16:                                         # 词太长则仍硬断
                    cut = -1
            if cut >= 0:
                out.append(line[:cut + 1].rstrip())
                line = line[cut + 1:].lstrip()
                w = sum(_cw(c, h) for c in line)
            else:
                out.append(line)
                line, w = '', 0.0
            if ch == ' ' and not line:
                continue
        line += ch
        w += cw
    out.append(line)
    return '\n'.join(shx(x) for x in out)


def table(s, x, y, cols, rows, header=1, h=H):
    """表格（左上角 x,y；列宽 cols）；返回表格下沿 y。行高按各格折行数自动加高。"""
    rows = [[wrap(c, cols[i], h) for i, c in enumerate(r)] for r in rows]
    s.items.append({'k': 'table', 'at': [x, y], 'cols': cols, 'rowh': ROWH, 'h': h, 'rows': rows, 'header': header})
    n = sum(max(1, max(c.count('\n') + 1 for c in r)) for r in rows)
    return y - n * ROWH


def ce_matrix(i):
    """联锁因果矩阵的一行：{动作列名: 'X'/''}。
    新项目：在 conventions.effect_columns 列出动作列，在每条联锁的 effects 中列出它触发的列（推荐，明确可审）。
    无 effects 时按动作文字归纳（青木子项目的规则：fuel_xv/n2_bypass/heat/load/alarm/permissive）。"""
    conv = M.get('conventions', {})
    cols = conv.get('effect_columns')
    if cols and 'effects' in i:
        return {c: ('X' if c in i['effects'] else '') for c in cols}
    import re
    a = i['actions']
    fx, bp, al = a.get('fuel_xv', ''), a.get('n2_bypass', ''), a.get('alarm', '')
    m8 = next((m['name'] for m in M.get('modes', []) if m['id'] == 'M8'), '')
    m8_ids = set(re.findall(r'I-\d\d', m8))
    for x, y in re.findall(r'I-(\d\d)~I-(\d\d)', m8):
        m8_ids |= {f'I-{k:02d}' for k in range(int(x), int(y) + 1)}
    return {
        '关燃料阀 XV-101/103~105': 'X' if fx.startswith('关') else '',
        '关 N₂ 阀 XV-102': 'X' if fx.startswith('关') else '',
        '开 N₂ 旁路 XV-201': 'X' if bp.startswith('开') else '',
        'N₂ 旁路保持关': 'X' if bp.startswith('保持关') else '',
        '切断炉加热 XY-301': 'X' if a.get('heat', '').startswith(('切断', '停')) else '',
        '负载禁能 XY-304': 'X' if a.get('load', '').startswith('禁能') else '',
        '声光报警 XA-401': 'X' if '声光' in al and '本机' not in al else '',
        '探测器本机报警': 'X' if '本机' in al else '',
        '禁止开燃料/升温': 'X' if a.get('permissive') else '',
        '转正常停机 M7': 'X' if 'M7' in fx else '',
        '执行紧急停机 M8': 'X' if 'M8' in fx or i['id'] in m8_ids else '',
        '执行超压停机 M9': 'X' if i['id'] in ('I-02', 'I-10') else '',
    }


def build(sheets, out, only=None):
    """sheets: {图号: 函数}；写出 spec 与图纸属性到 out 目录。"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for k in (only or list(sheets)):
        print('写出', sheets[k]().dump(out))


__all__ = ['CN', 'SMALL', 'H', 'ROWH', 'M', 'INL', 'INS', 'EQP', 'BND', 'IL', 'STYLE', 'CATALOG', 'use_model', 'shx', 'split_tag',
           'attach', 'Sheet', 'oval', 'ib', 'wrap', 'table', 'ce_matrix', 'build']
