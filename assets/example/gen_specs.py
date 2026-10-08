"""由 pid_model.json + 本文件中的版面坐标，生成各张 P&ID 的 PidBot 绘图 spec（JSON）。
坐标单位 mm，模型空间 = A3 图纸坐标（可绘区 x 25–415，y 5–292；右下 x≥235、y≤96 为标题栏/修订栏禁区）。
用法: python gen_specs.py <输出目录>   → 写出 P&ID-101.json 等
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = json.loads((HERE / 'pid_model.json').read_text(encoding='utf-8'))
INL = {x['tag']: x for x in M['inline']}
INS = {x['tag']: x for x in M['instruments']}
EQP = {x['tag']: x for x in M['equipment']}
BND = {x['id']: x for x in M['boundary']}

CN = 3.5      # 汉字字高（GB/T 14691 最小 3.5）
SMALL = 2.5   # 数字/字母字高

STYLE = {
    'ball_valve': 'Ball Valve Style', 'needle_valve': 'Needle Valve Style', 'check_valve': 'Check Valve Style',
    'filter': 'Filter Pipe Style', 'mfc': 'QMZ MFC Style', 'flow_switch': 'QMZ Flow Switch Style', 'cap': 'Cap Style',
}


def shx(t):
    """SHX 字体（gbenor/gbcbig）无下标字符与 en dash：改用 MText 堆叠与 ~"""
    for a, b in (('₂', r'\S^2;'), ('₄', r'\S^4;'), ('²', r'\S2^;'), ('–', '~'), ('Ø', '%%c')):
        t = t.replace(a, b)
    return t


def split_tag(tag):
    a, b = tag.split('-', 1)
    return a, b


class Sheet:
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

    OPC_LEN = 42.19   # Off Page Connector Style 长度（1.6875×25）

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
        props = {'PnID': self.no, 'Title': sh['title'], 'Description': sh.get('content', sh['title']),
                 'Area': '—', 'Author': '—', 'Revision': 'A', 'Stage': '方案设计', 'Scale': 'NTS',
                 'SheetNo': str(order.index(self.no) + 1), 'SheetTotal': str(len(order)),
                 'Checker': '—', 'Reviewer': '—', 'Approver': '—', 'IssueDate': M['meta']['date'], 'RevNote': '首版，供审查'}
        props = {k: v.replace('₂', '2').replace('₄', '4').replace('–', '~') for k, v in props.items()}   # 字段值不解释 MText 代码
        (Path(out) / f'{self.no}.props.json').write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding='utf-8')
        return p


# ================================================================ 标注位置（实测）：仪表圈中心=给定点；椭圆位号框比给定点右移约 3.5、上移约 3.8
def oval(x, y):
    """椭圆位号框（Oval Tag Style）中心 = 给定点"""
    return {'at': [x, y], 'style': 'Oval Tag Style'}


def ib(x, y):
    """ISA 现场仪表圈（Field Mounted Discrete Instrument Style）中心 = 给定点；不指定会取到 DCS 共享显示样式"""
    return {'at': [x, y], 'style': 'Field Mounted Discrete Instrument Style'}


# ================================================================ P&ID-101 五路燃料、备用口与 N₂ 保护旁路配气
def sheet_101():
    s = Sheet('P&ID-101')
    XH = 360                      # 混气集管 x
    X = dict(bl=40, hv=64, fl=88, tin=100, pcv=114, pi=128, tbp1=140, xv=154, mfc=192, tbp2=216, ck=232)
    rows = [('H2', 268, '0101', 'BL-H2', 'H₂ 气源（甲方一级减压后）'),
            ('N2', 240, '0102', 'BL-N2', 'N₂ 气源（甲方，兼驱动气）'),
            ('CO', 186, '0103', 'BL-CO', 'CO 气源（甲方一级减压后）'),
            ('CH4', 160, '0104', 'BL-CH4', 'CH₄ 气源（甲方一级减压后）'),
            ('CO2', 134, '0105', 'BL-CO2', 'CO₂ 气源（甲方一级减压后）')]
    YBP, YSP, YOUT = 218, 110, 100

    s.line('FG', [[XH, rows[0][1]], [XH, YOUT], [XH + 12, YOUT]], 'FG-0203-6-S1', anno=[XH, 213])

    for i, (fl, y, num, bid, label) in enumerate(rows):
        n = num[-1]
        ln = f'{fl}-{num}-6-S1'
        L = f'L{fl}'
        s.line(L, [[X['bl'] + 10, y], [XH, y]], ln, anno=[285, y])
        s.tie(bid, [X['bl'], y], L, 'start', label=label, label_at=[X['bl'] - 10, y + 6.5])
        s.hand(f'HV-10{n}', [X['hv'], y], L, anno=oval(X['hv'], y - 11))
        s.special(f'FL-10{n}', [X['fl'], y], L, anno=oval(X['fl'], y - 11))
        s.pcv(f'PCV-10{n}', [X['pcv'], y], L, anno=ib(X['pcv'] - 2, y + 15))
        s.bubble(f'PI-10{n}', [X['pi'], y + 14])
        s.line(f'LPI{n}', [[X['pi'], y], [X['pi'], y + 9]], ln, style='Secondary Style')
        s.tee(f'LPI{n}', L, True)
        s.items.append({'k': 'connect', 'line': f'LPI{n}', 'asset': f'PI-10{n}', 'ctx': 'end'})
        s.xv(f'XV-10{n}', [X['xv'], y], L, anno=ib(X['xv'], y + 15), fail_text_at=[X['xv'] - 7, y + 6])
        s.inst_inline(f'FIC-10{n}', [X['mfc'], y], L, anno=ib(X['mfc'], y + 14))
        s.hand(f'CK-10{n}', [X['ck'], y], L, anno=oval(X['ck'], y - 11))
        if i == 0:
            s.tee('FG', L, True)
        else:
            s.tee(L, 'FG', False)

    # N₂ 保护旁路 N2-0201
    yN2 = rows[1][1]
    s.line('LBP', [[X['tbp1'], yN2], [X['tbp1'], YBP], [X['tbp2'], YBP], [X['tbp2'], yN2]], 'N2-0201-6-S1')
    s.text(X['tbp1'] + 2, YBP - 5, 'N2-0201-6-S1', SMALL, 'ML')
    s.tee('LBP', 'LN2', True)
    s.tee('LBP', 'LN2', False)
    s.xv('XV-201', [168, YBP], 'LBP', anno=ib(168, YBP + 15), fail_text_at=[161, YBP + 6])
    s.hand('HV-202', [188, YBP], 'LBP', anno=oval(186, YBP + 9.5))
    s.text(180, YBP - 6, '限流 500 sccm', SMALL, 'ML')
    s.inst_inline('FSL-201', [206, YBP], 'LBP', anno=ib(209, YBP + 15))

    # 驱动 N₂ 取气 IN-0202（PCV-102 上游）→ P&ID-102
    s.line('LIN', [[X['tin'], yN2], [X['tin'], YBP], [75, YBP]], 'IN-0202-4-P1', style='Secondary Style')
    s.text(X['tin'] + 2, YBP + 8, 'IN-0202-4-P1', SMALL, 'ML')
    s.tee('LIN', 'LN2', True)
    s.opc('OPC-101-IN', [75, YBP], 'LIN', 'end', 'P&ID-102 驱动气', 'A', rot=180)

    # 备用口 SP-0106
    s.line('LSP', [[X['bl'] + 10, YSP], [XH, YSP]], 'SP-0106-6-S1', anno=[285, YSP])
    s.items.append({'k': 'asset', 'id': 'CAP-106', 'style': 'Cap Style', 'at': [X['bl'] + 10, YSP], 'rot': 180,
                    'props': {'Description': '备用口封堵帽（本期封堵）'}})
    s.items.append({'k': 'connect', 'line': 'LSP', 'asset': 'CAP-106', 'ctx': 'start'})
    s.text(X['bl'] - 10, YSP + 6.5, '备用气入口（本期封堵）', CN)
    s.hand('HV-106', [X['hv'], YSP], 'LSP', anno=oval(X['hv'], YSP - 11))
    s.hand('HV-107', [X['pcv'], YSP], 'LSP', anno=oval(X['pcv'], YSP - 11))
    s.hand('CK-106', [X['ck'], YSP], 'LSP', anno=oval(X['ck'], YSP - 11))
    s.tee('LSP', 'FG', False)
    s.text(130, YSP + 5, '启用可燃/有毒介质前须补装自动切断阀并评审', SMALL, 'ML')

    s.opc('OPC-101-FG', [XH + 12, YOUT], 'FG', 'end', 'P&ID-102 混气', 'B')

    s.text(30, 92, '\n'.join([
        '注：',
        '1. 管线号：物料代号-主项序号-外径(mm)-管道等级。S1：316L Φ6×1 无缝管，双卡套，0.6 MPa(g)/60 ℃；P1：PU Φ4 气管。',
        '2. XV 为 316L 气动隔膜阀（弹簧复位），执行机构上的“S”为二位三通先导电磁阀 XY（PLC DO，经安全继电器 UZ-401 串联切断）。',
        '3. FC：失电或失驱动气时关闭；FO：失电或失驱动气时打开。MFC 经 RS485 Modbus RTU 接 PLC，见 P&ID-104。',
        '4. 联锁见 P&ID-901，运行工况见 P&ID-902、P&ID-903。气瓶及一级减压由甲方提供。',
    ]), CN, 'TL', w=200)
    return s


def _more():
    import sheets_102_104 as m
    import sheets_000_900 as n
    return {'P&ID-000': n.sheet_000, 'P&ID-001': n.sheet_001, 'P&ID-102': m.sheet_102, 'P&ID-103': m.sheet_103,
            'P&ID-104': m.sheet_104, 'P&ID-901': n.sheet_901, 'P&ID-902': n.sheet_902, 'P&ID-903': n.sheet_903}


SHEETS = {'P&ID-101': sheet_101}

if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    SHEETS.update(_more())
    only = sys.argv[2:] or list(SHEETS)
    for k in only:
        print('写出', SHEETS[k]().dump(out))
