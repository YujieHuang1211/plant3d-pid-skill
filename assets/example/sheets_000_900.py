"""P&ID-000 封面目录、P&ID-001 图例、P&ID-901 联锁因果表、P&ID-902 运行工况表（由 gen_specs 导入）。
全部为普通 CAD 图形（文字/表格/图例符号块参照），不生成 Plant 智能对象，不进设备/仪表清单。
"""
import re

from gen_specs import Sheet, M, CN, shx

H = 3.5          # 表格汉字字高（GB/T 14691 最小 3.5）
ROWH = 5.6       # 每行文字高度占用


def _cw(ch, h):
    return h if ord(ch) > 0x2E80 else h * 0.62


def wrap(t, width, h=H):
    """按列宽折行：汉字宽≈字高，西文≈0.6 字高；西文单词不从中间断开（优先在空格、/、、处断）"""
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
    rows = [[wrap(c, cols[i], h) for i, c in enumerate(r)] for r in rows]
    s.items.append({'k': 'table', 'at': [x, y], 'cols': cols, 'rowh': ROWH, 'h': h, 'rows': rows, 'header': header})
    n = sum(max(1, max(c.count('\n') + 1 for c in r)) for r in rows)
    return y - n * ROWH


# ================================================================ P&ID-000 封面与图纸目录
def sheet_000():
    s = Sheet('P&ID-000')
    s.text(222, 262, '青木子纽扣电池测试台', 10, 'MC')
    s.text(222, 246, '管道及仪表流程图（P&ID）', 8, 'MC')
    s.text(222, 232, '单通道干气 SOFC 纽扣电池测试台　方案设计　A 版', 5, 'MC')
    rows = [['图号', '图名', '版次', '说明']]
    for sh in M['sheets']:
        rows.append([sh['no'], sh['title'], 'A', sh.get('content', '')])      # 不截断，由 table 折行
    y = table(s, 40, 220, [30, 75, 14, 191], rows)
    basis = ['设计依据：' + '；'.join(M['meta']['basis_doc']) + '。',
             '执行标准：PIP PIC001、ANSI/ISA-5.1、HG/T 20519.1/.2—2009、ISO 10628-1/-2。图例采用 PIP 公制符号，专用设备符号见 P&ID-001。',
             '图幅：A3 横向，GB/T 14689—2008 图框，GB/T 10609.1—2008 标题栏，比例 NTS。',
             '本图为方案设计阶段图纸，注“暂定”的设定值在 FAT 前确定。']
    s.text(40, y - 8, '\n'.join(wrap(b, 300, H) for b in basis), H, 'TL', w=310)
    return s


# ================================================================ P&ID-001 图例与符号说明
LEGEND = [
    # (样式, 比例, 名称, Plant 类, 来源)
    ('Ball Valve Style', None, '手动球阀（常开）', 'HandValves/BallValve', 'PIP 标准符号'),
    ('Ball Valve Closed Style', None, '手动球阀（常关，填黑）', 'HandValves/BallValve', 'PIP 标准符号'),
    ('Needle Valve Style', None, '针阀（限流）', 'HandValves/NeedleValve', 'PIP 标准符号'),
    ('Needle Valve Closed Style', None, '针阀（常关）', 'HandValves/NeedleValve', 'PIP 标准符号'),
    ('Check Valve Style', None, '止回阀', 'HandValves/CheckValve', 'PIP 标准符号'),
    ('Filter Pipe Style', None, '管道过滤器', 'PipingSpecialtyItems/FilterPipe', 'PIP 标准符号'),
    ('Cap Style', None, '封堵帽', 'Fittings/Cap', 'PIP 标准符号'),
    ('Diaphragm Valve Style', None, '隔膜阀阀体', 'ControlValve', 'PIP 标准符号'),
    ('QMZ Diaphragm Solenoid Actuator', None, '气动隔膜执行机构＋先导电磁阀（S）', 'Actuators/Diaphragm', '项目自定义符号'),
    ('PressureReducingRegulator Style', None, '自力式减压阀（执行机构）', 'Actuators/PressureReducingRegulator', 'PIP 标准符号'),
    ('QMZ MFC Style', None, '质量流量控制器 MFC（一体化）', 'MassFlowController（项目新增类）', '项目自定义符号'),
    ('QMZ Flow Switch Style', None, '在线流量开关', 'InlineInstruments/FlowSwitch', '项目自定义符号'),
    ('Field Mounted Discrete Instrument Style', None, '现场仪表', 'GeneralInstrumentSymbols', 'PIP 标准符号（ISA-5.1）'),
    ('Primary Loc Accessible PLC Style', None, 'PLC 功能及软件联锁 I-xx（PLC 执行）', 'GeneralInstrumentSymbols', 'PIP 标准符号（ISA-5.1）'),
    ('Field Mounted Discrete Hardware Interlock Style', None, '硬件联锁（安全继电器）', 'GeneralInstrumentSymbols', 'PIP 标准符号（ISA-5.1）'),
    ('Off Page Connector Style', None, '跨图连接器', 'Connectors/OffPageConnector', 'PIP 标准符号'),
    ('QMZ Battery Limit Style', None, '界区接口（甲方供/去向）', 'TieInPoint（项目新增类）', '项目自定义符号'),
    ('QMZ Condensate Cup Style', 0.5, '尾气冷凝收集杯', 'Tanks/Vessel', '项目自定义符号'),
    ('QMZ Electronic Load Style', 0.4, '直流电子负载', 'ElectronicLoad（项目新增类）', '项目自定义符号'),
    ('QMZ Tube Furnace Style', 0.18, '管式炉（开启式单温区）', 'Furnaces/Furnace', '项目自定义符号'),
    ('QMZ Coin Cell Fixture Style', 0.35, '纽扣电池测试夹具', 'TestFixture（项目新增类）', '项目自定义符号'),
]
# 大符号的行高（行数）与水平偏移：按 2026-10-07 首版出图实测尺寸（收集杯约 15 mm 高、负载约 34×16、炉约 100×50、
# 夹具插入点在右端），保证符号落在本行格内、不越出表格左边
# 第三项为竖向偏移：执行机构插入点在阀杆底端、图形向上约 9.5 mm，下移半个高度使其落在本行中间（否则压到上一行阀体）
SYMFIT = {'QMZ Condensate Cup Style': (2, 0, 0), 'QMZ Electronic Load Style': (2, 0, 0),
          'QMZ Tube Furnace Style': (2, 0, 0), 'QMZ Coin Cell Fixture Style': (1, 8, 0),
          'QMZ Diaphragm Solenoid Actuator': (2, 0, -4.75)}


def sheet_001():
    s = Sheet('P&ID-001')
    s.text(30, 288, '图例与符号说明', 5, 'ML')
    cols = [24, 68, 54, 40]
    rows = [['符号', '名称', 'Plant 类别', '来源']]
    def padded(st, name):
        need = SYMFIT.get(st, (1, 0, 0))[0]
        have = wrap(name, cols[1]).count('\n') + 1
        return name + '\n' * max(0, need - have)

    for st, sc, name, cls, src in LEGEND:
        rows.append(['', padded(st, name), cls, src])
    ytop = 280
    table(s, 30, ytop, cols, rows)
    # 符号放进第一列各行（表头一行 + 每行按折行数计高）
    y = ytop - ROWH
    for st, sc, name, cls, src in LEGEND:
        # 名称/类别列可能折行：按最多行数估算本行高度（与 table 的折行一致）
        n = max(wrap(padded(st, name), cols[1]).count('\n'), wrap(cls, cols[2]).count('\n'), wrap(src, cols[3]).count('\n')) + 1
        hgt = n * ROWH
        _, dx, dy = SYMFIT.get(st, (1, 0, 0))
        it = {'k': 'sym', 'style': st, 'at': [30 + cols[0] / 2 + dx, y - hgt / 2 + dy], 'layer': '注释'}
        if sc:
            it['scale'] = sc
        s.items.append(it)
        y -= hgt
    # 右栏：线型、仪表字母、编号规则、缩写
    x2 = 222
    lines_tbl = [['线型', '含义'],
                 ['粗实线 0.5', '主工艺管线（316L Φ6，S1）'], ['中实线 0.35', '驱动 N₂（PU Φ4，P1）／仪表引压线'],
                 ['细虚线', '电信号（硬接线）'], ['细线带圆圈', '软件/通信链路（RS485、RS232、以太网）']]
    y2 = table(s, x2, 280, [36, 150], lines_tbl)
    letters = [['代号', '含义（ISA-5.1）'],
               ['FIC', '流量指示控制（MFC，一体化）'], ['FSL', '流量开关低'], ['PCV / PI / PT', '自力式压力调节阀／压力表／压力变送器'],
               ['PI / PAHH', '压力指示／压力高高报警联锁（PLC）'], ['XV / XY', '开关阀／开关阀先导电磁阀'],
               ['TE / TT / TI', '测温元件／温度变送器／温度指示'], ['TIC / TSHH / TAHH / TAH', '温度控制／超温开关／温度高高／温度高'],
               ['AIT', '气体分析指示变送（探测器）'], ['EI / II', '电压指示／电流指示'],
               ['HS / XA / UZ', '手动开关（急停、复位）／声光报警／安全继电器'], ['I-xx', '联锁编号，见 P&ID-901'],
               ['FC / FO / NC', '失电失气关／失电失气开／常关']]
    y2 = table(s, x2, y2 - 4, [44, 142], letters)
    s.text(x2, y2 - 5, '\n'.join([
        wrap('管线号：物料代号-主项序号-外径(mm)-管道等级，例 H2-0101-6-S1。物料代号：H2 氢气、N2 氮气、CO、CH4、CO2、SP 备用气、IN 驱动用氮气、FG 混合燃料气、AG 阳极尾气、DR 冷凝液。', 186),
        wrap('位号：仪表 字母代号-回路号（回路百位：1 配气，2 旁路/混气，3 炉/夹具/尾气/电测，4 安全）；设备 F 炉、X 夹具、JL 电子负载、V 容器；手阀 HV、止回阀 CK、过滤器 FL、界区接口 TP。', 186),
        wrap('项目自定义符号已在项目符号库中定义类别、连接方式、标注样式及属性。', 186),
    ]), H, 'TL', w=188)
    return s


# ================================================================ P&ID-901 联锁因果表
def sheet_901():
    """因果矩阵：行＝联锁原因，列＝动作，X＝触发。全文（检测方式、各动作说明、依据）见《联锁因果表》xlsx。
    与 xlsx“因果矩阵”页同一归纳规则（pidlib.ce_matrix）。图面须在修订栏（顶边 89 mm）之上结束。"""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2] / 'scripts'))
    import pidlib
    pidlib.M.update(M)          # ce_matrix 读取模型里的 conventions
    ce_matrix = pidlib.ce_matrix
    s = Sheet('P&ID-901')
    s.text(30, 288, '联锁因果矩阵（C&E）', 5, 'ML')
    effects = list(ce_matrix(M['interlocks'][0]).keys())
    cols = [14, 66, 28] + [17] * len(effects) + [44]
    rows = [['编号', '原因', '设定值'] + effects + ['复位']]
    for i in M['interlocks']:
        rows.append([i['id'], i['cause'], i['setpoint']] + list(ce_matrix(i).values()) + [i['reset']])
    y = table(s, 28, 280, cols, rows)
    notes = ['注：1. X 表示该原因触发该动作。叠加故障时压力保护优先：I-02 或 I-10 成立时 N₂ 旁路保持关闭。',
             '2. 外部市电失电由 UPS 干接点 JSL-401 送 PLC，执行 M8；完全断电或失驱动气时 FC 阀关闭、FO 阀打开。',
             '3. 检测方式及动作说明见《联锁因果表》和《运行工况与联锁说明》；注“暂定”的设定值在 FAT 前确定。']
    s.text(30, y - 5, '\n'.join(wrap(n, 200) for n in notes), H, 'TL', w=205)
    return s


# ================================================================ P&ID-902/903 运行工况表（两张，避免表格压标题栏）
MODE_HEAD = ['编号', '工况', '燃料切断阀', 'XV-102', 'N₂ 旁路 XV-201', 'N₂ 气源', 'MFC', '加热', '负载', '许可条件', '转出条件']
MODE_COLS = [14, 36, 32, 16, 34, 26, 40, 30, 30, 50, 46]


def _modes_sheet(no, ids, title):
    s = Sheet(no)
    s.text(30, 288, title, 5, 'ML')
    rows = [MODE_HEAD] + [[m['id'], m['name'], m['fuel_xv'], m['xv102'], m['bypass'], m['n2_source'], m['mfc'], m['heat'], m['load'], m['permissive'], m['exit']]
                          for m in M['modes'] if m['id'] in ids]
    y = table(s, 28, 280, MODE_COLS, rows)
    s.text(30, y - 5, '\n'.join([wrap('注：PLC 为非安全 PLC，执行顺序控制与软件联锁；硬件安全许可见 P&ID-104。工况转换须经 HMI 确认，来电不自动重启。', 200),
                                  wrap('联锁见 P&ID-901。', 200)]), H, 'TL', w=205)
    return s


def sheet_902():
    return _modes_sheet('P&ID-902', {'M0', 'M1', 'M2', 'M3', 'M4', 'M5'}, '运行工况表（一）：M0~M5 各工况阀位、流量、加热、负载、许可与转出条件')


def sheet_903():
    return _modes_sheet('P&ID-903', {'M6', 'M7', 'M8', 'M9', 'M10'}, '运行工况表（二）：M6~M10 各工况阀位、流量、加热、负载、许可与转出条件')
