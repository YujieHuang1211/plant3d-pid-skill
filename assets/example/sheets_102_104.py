"""P&ID-102 / 103 / 104 版面（由 gen_specs.py 导入）。坐标单位 mm，A3 模型空间。"""
from gen_specs import Sheet, INS, M, CN, SMALL, ib, oval

NOTE_SIG = '信号线：虚线＝电信号（硬接线），带圆圈虚线＝软件/通信链路。'
IL = {x['id']: x for x in M['interlocks']}


# ================================================================ P&ID-102 驱动 N₂、混气与阳极进气
def sheet_102():
    s = Sheet('P&ID-102')
    Y0 = 250
    s.line('LIN2', [[75, Y0], [150, Y0]], 'IN-0202-4-P1', style='Secondary Style', anno=[125, Y0])
    s.opc('OPC-102-IN', [75, Y0], 'LIN2', 'start', 'P&ID-101 驱动气', 'A', rot=180)
    s.pair('OPC-102-IN', 'OPC-101-IN')
    s.pcv('PCV-202', [98, Y0], 'LIN2', anno=ib(96, Y0 + 15))
    s.bubble('PI-202', [112, Y0 + 14])
    s.line('LPI202', [[112, Y0], [112, Y0 + 9]], 'IN-0202-4-P1', style='Secondary Style')
    s.tee('LPI202', 'LIN2', True)
    s.connect('LPI202', 'PI-202', 'end')
    s.line('LMAN', [[150, 280], [150, 196]], 'IN-0202-4-P1', style='Secondary Style')
    s.tee('LIN2', 'LMAN', False)
    s.text(155, 287, '驱动 N₂ 分配块（0.4~0.6 MPa(g)）', CN)
    pilots = [('XY-101', 'XV-101 H₂ 切断（FC）'), ('XY-102', 'XV-102 N₂ 切断（FC）'), ('XY-103', 'XV-103 CO 切断（FC）'),
              ('XY-104', 'XV-104 CH₄ 切断（FC）'), ('XY-105', 'XV-105 CO₂ 切断（FC）'), ('XY-201', 'XV-201 N₂ 保护旁路（FO）')]
    for k, (tag, txt) in enumerate(pilots):
        y = 280 - k * 16.8
        lid = f'LP{k}'
        s.line(lid, [[150, y], [185, y]], 'IN-0202-4-P1', style='Secondary Style')
        s.tee(lid, 'LMAN', True)
        s.bubble(tag, [190, y])
        s.connect(lid, tag, 'end')
        io = INS[tag].get('io', '')
        s.text(198, y, f'{txt}；PLC {io}，经 UZ-401 许可；见 P&ID-101', SMALL, 'ML')
    s.text(155, 188, '先导电磁阀为二位三通常闭 24 VDC（亚德客 3V1），排气引至柜外。', SMALL, 'ML')

    Y1 = 140
    s.line('FG2', [[75, Y1], [300, Y1]], 'FG-0203-6-S1', anno=[245, Y1])
    s.opc('OPC-102-FG', [75, Y1], 'FG2', 'start', 'P&ID-101 混气', 'B', rot=180)
    s.pair('OPC-102-FG', 'OPC-101-FG')
    s.opc('OPC-102-AN', [300, Y1], 'FG2', 'end', 'P&ID-103 阳极进气', 'C')
    s.text(80, Y1 - 8, '混合燃料气，低死容积段（受控容积 ≤0.2 L），总流量 ≤500 sccm（程序限定）', SMALL, 'ML')
    s.line('LPT', [[150, Y1], [150, Y1 + 17]], 'FG-0203-6-S1', style='Secondary Style')
    s.tee('LPT', 'FG2', True)
    s.bubble('PT-201', [150, Y1 + 22])
    s.connect('LPT', 'PT-201', 'end')
    s.plc('PI-201', [185, Y1 + 22])
    s.plc('PAHH-201', [215, Y1 + 22])
    s.ilock('I-02', [250, Y1 + 22])
    s.ilock('I-10', [250, Y1 + 42])
    s.sigc('S201a', [[155, Y1 + 22], [180, Y1 + 22]], 'Electrical Style', 'PT-201', 'PI-201')
    s.sigc('S201b', [[190, Y1 + 22], [210, Y1 + 22]], 'Software Style', 'PI-201', 'PAHH-201')
    s.sigc('S201c', [[220, Y1 + 22], [245, Y1 + 22]], 'Software Style', 'PAHH-201', 'I-02')
    s.sigc('S201d', [[185, Y1 + 27], [185, Y1 + 42], [245, Y1 + 42]], 'Software Style', 'PI-201', 'I-10')
    s.text(118, Y1 + 31, '0~5 kPa(g)，4~20 mA（AI01）', SMALL, 'ML')
    s.text(258, Y1 + 22, 'I-02 阳极压力高高 3 kPa(g)（暂定）：', SMALL, 'ML')
    s.text(258, Y1 + 17, '切燃料、切加热、负载卸载，不送 N₂', SMALL, 'ML')
    s.text(258, Y1 + 42, 'I-10 PT-201 信号丢失：同 I-02', SMALL, 'ML')

    s.text(30, 92, '\n'.join([
        '注：',
        '1. 驱动 N₂ 取自 N₂ 二级减压上游（P&ID-101 T-IN），供压须 ≥0.45 MPa(g)；先导阀失电或驱动气中断时，FC 阀关闭、FO 阀打开。',
        '2. PT-201 取压点靠近夹具冷端阳极入口；阳极正常 0~0.3 kPa(g)，联锁值须低于玻璃封接允许压，FAT 前冻结。',
        '3. ' + NOTE_SIG + '联锁动作见 P&ID-901。',
    ]), CN, 'TL', w=200)
    return s


# ================================================================ P&ID-103 管式炉、夹具、尾气与电测
def sheet_103():
    s = Sheet('P&ID-103')
    s.equip('F-301', 'QMZ Tube Furnace Style', [220, 200], anno=[205, 178])
    s.equip('X-301', 'QMZ Coin Cell Fixture Style', [225, 200], anno=[207, 222])
    s.equip('V-301', 'QMZ Condensate Cup Style', [90, 150], anno=[68, 150])
    s.equip('JL-301', 'QMZ Electronic Load Style', [330, 200], anno=[330, 185])
    s.nozzle('X-301', 'N-AN-IN', [183, 202], 180)
    s.nozzle('X-301', 'N-AN-OUT', [183, 198], 180)
    s.nozzle('V-301', 'N-V-IN', [87, 157], 90)
    s.nozzle('V-301', 'N-V-OUT', [95, 152], 0)
    s.nozzle('V-301', 'N-V-DR', [90, 143], 270)
    s.line('FG3', [[75, 250], [130, 250], [130, 202], [183, 202]], 'FG-0203-6-S1', anno=[102, 250])
    s.opc('OPC-103-AN', [75, 250], 'FG3', 'start', 'P&ID-102 混气', 'C', rot=180)
    s.pair('OPC-103-AN', 'OPC-102-AN')
    s.connect('FG3', 'N-AN-IN', 'end')
    s.line('AG1', [[183, 198], [150, 198], [150, 172], [87, 172], [87, 157]], 'AG-0301-6-S1', anno=[120, 172])
    s.connect('AG1', 'N-AN-OUT', 'start')
    s.connect('AG1', 'N-V-IN', 'end')
    # 尾气出口线放在排液线（y=125）下方 25 mm，避开 HV-301 位号（y≈114）
    s.line('AG2', [[95, 152], [110, 152], [110, 100], [60, 100]], 'AG-0302-6-S1', anno=[85, 100])
    s.connect('AG2', 'N-V-OUT', 'start')
    s.tie('BL-AG', [50, 100], 'AG2', 'end', rot=180, label='阳极尾气至甲方尾气排放/处理接口（近常压，不得抽负压）', label_at=[30, 107])
    s.line('DR1', [[90, 143], [90, 125], [60, 125]], 'DR-0303-6-S1')
    s.connect('DR1', 'N-V-DR', 'start')
    s.hand('HV-301', [75, 125], 'DR1', anno=oval(75, 125 - 11))
    s.tie('BL-DR', [50, 125], 'DR1', 'end', rot=180, label='冷凝液人工排放至甲方容器（HV-301 常关）', label_at=[30, 132])
    s.text(93, 136, 'DR-0303-6-S1', SMALL, 'ML')
    s.text(232, 181, '阴极侧敞开（环境空气）', SMALL, 'ML')   # 炉框下沿以下，避开加热丝
    s.bubble('TIC-301', [240, 235])
    s.bubble('TSHH-301', [262, 235])
    s.bubble('XY-301', [218, 245])                       # 炉加热许可接触器（PLC DO08，经 UZ-401 串联切断）
    s.sigc('S301c', [[218, 240], [218, 214]], 'Electrical Style', 'XY-301', 'F-301')
    s.text(225, 245, 'XY-301 炉加热许可（DO08）', SMALL, 'ML')
    s.sigc('S301a', [[240, 230], [240, 214]], 'Electrical Style', 'TIC-301', 'F-301')
    s.sigc('S301b', [[262, 230], [262, 222], [248, 222], [248, 214]], 'Electrical Style', 'TSHH-301', 'F-301')
    s.text(272, 248, 'TIC-301 炉自带温控（含 TE-301），RS485 Modbus → PLC（COM06）', SMALL, 'ML')   # 上移，避开 EI/II-304
    s.text(272, 243, 'TSHH-301 炉超温硬接点 → PLC DI09 → I-08', SMALL, 'ML')
    s.bubble('TE-302', [225, 168])
    s.sigc('S302a', [[225, 173], [225, 196]], 'Electrical Style', 'TE-302', 'X-301')
    s.plc('TI-302', [255, 168])
    s.plc('TAHH-302', [282, 168])
    s.ilock('I-09', [310, 168])
    s.sigc('S302b', [[230, 168], [250, 168]], 'Electrical Style', 'TE-302', 'TI-302')
    s.sigc('S302c', [[260, 168], [277, 168]], 'Software Style', 'TI-302', 'TAHH-302')
    s.sigc('S302d', [[287, 168], [305, 168]], 'Software Style', 'TAHH-302', 'I-09')
    s.text(212, 157, 'S 型热电偶 0~1200 ℃（TC01）；TAHH 950 ℃（暂定）/断线', SMALL, 'ML')
    s.bubble('TE-303', [186, 232])
    s.bubble('TT-303', [165, 232])
    s.plc('TAH-303', [165, 252])
    s.sigc('S303a', [[186, 227], [186, 203]], 'Electrical Style', 'TE-303', 'X-301')
    s.sigc('S303b', [[181, 232], [170, 232]], 'Electrical Style', 'TE-303', 'TT-303')
    s.sigc('S303c', [[165, 237], [165, 247]], 'Electrical Style', 'TT-303', 'TAH-303')
    s.text(172, 258, '冷端 Pt100 0~200 ℃，4~20 mA（AI02），TAH 120 ℃（暂定）', SMALL, 'ML')
    s.sigc('SK1', [[226.6, 203], [314, 203]], 'Electrical Style', 'X-301', 'JL-301')
    s.sigc('SK2', [[226.6, 197], [314, 197]], 'Electrical Style', 'X-301', 'JL-301')
    s.text(268, 207, 'Kelvin 四线：I+/I−（载流）、V+/V−（测压）', SMALL, 'ML')
    s.plc('EI-304', [320, 230])
    s.plc('II-304', [342, 230])
    s.bubble('XY-304', [372, 215])
    s.sigc('S304a', [[320, 225], [320, 208]], 'Software Style', 'EI-304', 'JL-301')
    s.sigc('S304b', [[342, 225], [342, 208]], 'Software Style', 'II-304', 'JL-301')
    s.sigc('S304c', [[372, 210], [372, 200], [346, 200]], 'Electrical Style', 'XY-304', 'JL-301')
    s.text(272, 253, 'FT6211A：RS232/SCPI 经隔离串口服务器 → PLC（COM07）', SMALL, 'ML')
    s.text(378, 207, 'DO09 禁能', SMALL, 'ML')

    s.text(30, 92, '\n'.join([
        '注：',
        '1. 管式炉为甲方指定型号（科晶 OTF-1200X-S-Φ50），炉自带温控、炉热偶与超温保护；样品温度由独立 S 型热电偶 TE-302 测量并记录。',
        '2. 夹具为刚玉管玻璃封接结构，冷端在炉膛外；阳极进/出气在冷端，阴极侧敞开，不设阴极供气。',
        '3. 尾气去向、排风与尾气处理由甲方负责；含 CO 尾气不得排入室内。' + NOTE_SIG,
    ]), CN, 'TL', w=200)
    return s


SHORT_CAUSE = {'I-07': 'N₂ 供应失效（FSL-201 未证明 / FIC-102 失流）'}


# ================================================================ P&ID-104 安全检测、急停与控制系统接口
def sheet_104():
    s = Sheet('P&ID-104')
    # 安全继电器须先于连到它的信号线创建（连接时按 id 查找对象）
    s.items.append({'k': 'asset', 'id': 'UZ-401', 'style': 'Field Mounted Discrete Hardware Interlock Style', 'at': [150, 216],
                    'props': {'Type': 'UZ', 'LoopNumber': '401', 'Description': INS['UZ-401']['desc'], 'BasisRef': INS['UZ-401']['src'], 'IOPoint': INS['UZ-401']['io']}, 'auto': True})
    dets = [('AIT-401', 'CO 0~200 ppm：AAH 10 / AAHH 20 ppm'), ('AIT-402', 'H₂ 0~100 %LEL：AAH 10 / AAHH 20 %LEL'),
            ('AIT-403', 'CH₄ 0~100 %LEL：AAH 10 / AAHH 20 %LEL')]
    # UZ-401 菱形（中心 150,216）实测顶点：左 (145,216)、上 (150,220.8)、下 (150,211.1)、右 (155,216)。
    # 信号线终点必须落在顶点或边上，否则图面看似未连接：探测器经汇流线进上顶点，急停进左顶点，复位进左下边
    for k, (tag, txt) in enumerate(dets):
        y = 262 - k * 16
        s.bubble(tag, [50, y])
        s.text(30, y - 9, txt, SMALL, 'ML')
        xd = 128 - 4 * k        # 上面的探测器在最右侧下行，水平线互不交叉
        s.sigc(f'SD{k}', [[55, y], [xd, y], [xd, 226], [150, 226], [150, 220.8]], 'Electrical Style', tag, 'UZ-401')
    s.bubble('HS-401', [50, 190])
    s.text(30, 181, '急停（双触点）', CN, 'ML')
    s.sigc('SHS1', [[55, 190], [134, 190], [134, 216], [145, 216]], 'Electrical Style', 'HS-401', 'UZ-401')
    s.bubble('HS-402', [50, 165])
    s.text(30, 156, '复位按钮', CN, 'ML')
    s.sigc('SHS2', [[55, 165], [140, 165], [140, 213.5], [147.5, 213.5]], 'Electrical Style', 'HS-402', 'UZ-401')
    s.text(157, 204, 'UZ-401 安全继电器：双通道，手动复位；串联在 PLC DO 之后', SMALL, 'ML')
    for iid, y in (('I-01', 262), ('I-03', 246), ('I-04', 230), ('I-05', 214)):
        s.ilock(iid, [200, y], hardware=True)
        s.sigc(f'SU{iid}', [[155, 216], [175, 216], [175, y], [195, y]], 'Electrical Style', 'UZ-401', iid)
        s.text(208, y, IL[iid]['cause'], SMALL, 'ML')
    s.text(208, 274, '硬件撤销许可：燃料 XV 关，XV-201 开，炉加热 XY-301 断，负载 XY-304 禁能', SMALL, 'ML')
    s.plc('PLC-401', [150, 140], 'S7-1200 CPU1214C')
    s.items.append({'k': 'asset', 'id': 'HMI-401', 'style': 'Primary Loc Accessible Discrete Instrument Style', 'at': [210, 140],
                    'props': {'Type': 'HMI', 'LoopNumber': '401', 'Description': INS['HMI-401']['desc'], 'BasisRef': INS['HMI-401']['src']}, 'auto': True})
    s.bubble('XA-401', [90, 140])
    s.sigc('SPLC1', [[150, 211], [150, 145]], 'Electrical Style', 'UZ-401', 'PLC-401')
    s.sigc('SPLC2', [[155, 140], [205, 140]], 'Software Style', 'PLC-401', 'HMI-401')
    s.sigc('SPLC3', [[145, 140], [95, 140]], 'Electrical Style', 'PLC-401', 'XA-401')
    s.text(158, 152, 'PLC-401 S7-1200 CPU1214C（顺序控制与软件联锁，非安全 PLC）', SMALL, 'ML')
    s.text(216, 147, 'HMI-401 昆仑通态 TPC1031Nt 10″；以太网 VNC → 台式电脑；CSV 导出', SMALL, 'ML')
    s.text(70, 130, 'XA-401 总声光报警（DO10）', SMALL, 'ML')
    for iid, x, y in (('I-06', 200, 122), ('I-07', 200, 110), ('I-08', 200, 98), ('I-11', 300, 122), ('I-12', 300, 110), ('I-13', 300, 98)):
        s.ilock(iid, [x, y])
        s.text(x + 8, y, SHORT_CAUSE.get(iid, IL[iid]['cause']), SMALL, 'ML')   # 两列间距 100 mm，长原因用简写，全文见 P&ID-901
    s.sigc('SIL', [[150, 135], [150, 122], [195, 122]], 'Software Style', 'PLC-401', 'I-06')
    s.bubble('JSL-401', [90, 118])
    s.sigc('SJSL', [[95, 118], [147, 118], [147, 135]], 'Electrical Style', 'JSL-401', 'PLC-401')   # PLC 框 145~155×135~145，进下边，不落在角点
    s.text(64, 108, 'JSL-401 UPS 市电失电接点（DI06）→ I-13 → M8', SMALL, 'ML')
    s.text(240, 200, '\n'.join([
        '通信：CM1241 RS485 Modbus RTU 一条总线 6 节点：',
        'FIC-101~105（P&ID-101）、TIC-301（P&ID-103）；',
        'FT6211A RS232/SCPI 经隔离串口服务器 → 以太网；',
        'PLC—HMI—台式电脑 以太网（交换机）。',
    ]), SMALL, 'TL', w=170)
    s.text(30, 92, '\n'.join([
        '注：',
        '1. 探测器报警与故障接点串入 UZ-401 安全许可，并同时接入 PLC DI03~DI05 记录；故障按失去许可处理。',
        '2. UZ-401 硬件撤销燃料与加热许可；PLC 执行顺序控制与软件联锁（I-02、I-06~I-13），不作安全 PLC 用。',
        '3. ' + NOTE_SIG + '全部联锁原因与动作见 P&ID-901，运行工况见 P&ID-902、P&ID-903。',
    ]), CN, 'TL', w=200)
    return s
