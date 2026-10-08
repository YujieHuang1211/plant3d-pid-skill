"""独立验证项目的测试图 spec：每类对象各取一个代表，含真实连接，供“保存→重开”核对。
用法: python test_specs.py <输出目录>    → TEST-01.json（全类型）、TEST-02.json（跨图配对）及 *.props.json
"""
import json
import sys
from pathlib import Path

import gen_specs as G
from gen_specs import Sheet, ib, oval, SMALL, CN

# 测试图不在模型的图纸清单里：dump 时补一条
G.M['sheets'] += [{'no': 'TEST-01', 'title': '验证：全类型对象与连接'}, {'no': 'TEST-02', 'title': '验证：跨图连接器配对'}]


def t01():
    s = Sheet('TEST-01')
    # 支路：界区旗 → 球阀 → 过滤器 → 减压阀+压力表 → 气动隔膜阀(自定义执行机构) → MFC → 止回阀 → 集管
    y = 260
    s.line('L1', [[50, y], [300, y]], 'H2-0101-6-S1', anno=[255, y])
    s.tie('BL-H2', [40, y], 'L1', 'start', label='界区进口旗', label_at=[30, y + 6])
    s.hand('HV-101', [64, y], 'L1', anno=oval(64, y - 11))
    s.special('FL-101', [88, y], 'L1', anno=oval(88, y - 11))
    s.pcv('PCV-101', [114, y], 'L1', anno=ib(112, y + 15))
    s.bubble('PI-101', [128, y + 14])
    s.line('LPI', [[128, y], [128, y + 9]], 'H2-0101-6-S1', style='Secondary Style')
    s.tee('LPI', 'L1', True)
    s.connect('LPI', 'PI-101', 'end')
    s.xv('XV-101', [154, y], 'L1', anno=ib(154, y + 15), fail_text_at=[147, y + 6])
    s.inst_inline('FIC-101', [192, y], 'L1', anno=ib(192, y + 14))
    s.hand('CK-101', [232, y], 'L1', anno=oval(232, y - 11))
    # 集管与支路三通（起点在线上、终点在线上）
    s.line('FG', [[300, y], [300, 200], [330, 200]], 'FG-0203-6-S1', anno=[300, 230])
    s.tee('FG', 'L1', True)
    s.line('L2', [[50, 220], [300, 220]], 'N2-0102-6-S1', anno=[255, 220])
    s.tie('BL-N2', [40, 220], 'L2', 'start')
    s.tee('L2', 'FG', False)
    # 旁路：起点、终点都在 L2 上；FO 阀、常关针阀（填黑）、流量开关
    s.line('LBP', [[120, 220], [120, 205], [220, 205], [220, 220]], 'N2-0201-6-S1')
    s.tee('LBP', 'L2', True)
    s.tee('LBP', 'L2', False)
    s.xv('XV-201', [150, 205], 'LBP', anno=ib(150, 190), fail_text_at=[143, 211])
    s.hand('HV-107', [175, 205], 'LBP', anno=oval(175, 194))   # 模型中为 NC → 应出填黑符号
    s.inst_inline('FSL-201', [200, 205], 'LBP', anno=ib(205, 190))
    # 封堵帽
    s.line('LSP', [[50, 180], [120, 180]], 'SP-0106-6-S1')
    s.items.append({'k': 'asset', 'id': 'CAP-106', 'style': 'Cap Style', 'at': [50, 180], 'rot': 180, 'props': {'Description': '封堵帽'}})
    s.connect('LSP', 'CAP-106', 'start')
    s.hand('HV-106', [80, 180], 'LSP', anno=oval(80, 169))
    s.tie('BL-AG', [130, 180], 'LSP', 'end', rot=0)
    # 跨图连接器（去 TEST-02）
    s.opc('OPC-T01', [330, 200], 'FG', 'end', 'TEST-02', 'A')
    # 设备 + 管嘴 + 管线到管嘴
    s.equip('F-301', 'QMZ Tube Furnace Style', [250, 130], anno=[235, 108])
    s.equip('X-301', 'QMZ Coin Cell Fixture Style', [255, 130], anno=[237, 152])
    s.nozzle('X-301', 'N-IN', [213, 132], 180)
    s.nozzle('X-301', 'N-OUT', [213, 128], 180)
    s.line('LAN', [[150, 160], [190, 160], [190, 132], [213, 132]], 'FG-0203-6-S1')
    s.connect('LAN', 'N-IN', 'end')
    s.equip('V-301', 'QMZ Condensate Cup Style', [120, 120], anno=[98, 120])
    s.nozzle('V-301', 'N-VIN', [117, 127], 90)
    s.nozzle('V-301', 'N-VDR', [120, 113], 270)
    s.line('LAG', [[213, 128], [180, 128], [180, 140], [117, 140], [117, 127]], 'AG-0301-6-S1')
    s.connect('LAG', 'N-OUT', 'start')
    s.connect('LAG', 'N-VIN', 'end')
    s.line('LDR', [[120, 113], [120, 100], [80, 100]], 'DR-0303-6-S1')
    s.connect('LDR', 'N-VDR', 'start')
    s.hand('HV-301', [100, 100], 'LDR', anno=oval(100, 89 + 0))
    s.tie('BL-DR', [70, 100], 'LDR', 'end', rot=180)
    # 电测：负载 + 两根电信号线（设备—设备）
    s.equip('JL-301', 'QMZ Electronic Load Style', [350, 130], anno=[350, 115])
    s.sigc('SK1', [[256.6, 133], [334, 133]], 'Electrical Style', 'X-301', 'JL-301')
    s.sigc('SK2', [[256.6, 127], [334, 127]], 'Electrical Style', 'X-301', 'JL-301')
    # 仪表回路：现场仪表 → PLC 功能 → 软件联锁；硬件联锁
    s.bubble('TE-302', [255, 160])
    s.sigc('ST1', [[255, 155], [255, 133]], 'Electrical Style', 'TE-302', 'X-301')
    s.plc('TI-302', [285, 160])
    s.plc('TAHH-302', [312, 160])
    s.ilock('I-09', [340, 160])
    s.ilock('I-01', [370, 160], hardware=True)
    s.sigc('ST2', [[260, 160], [280, 160]], 'Electrical Style', 'TE-302', 'TI-302')
    s.sigc('ST3', [[290, 160], [307, 160]], 'Software Style', 'TI-302', 'TAHH-302')
    s.sigc('ST4', [[317, 160], [335, 160]], 'Software Style', 'TAHH-302', 'I-09')
    s.text(30, 60, 'TEST-01 验证图：每类对象一个代表；保存后与重开后分别核对位号、智能属性、真实连接。', CN, 'ML')
    return s


def t02():
    s = Sheet('TEST-02')
    s.line('FG2', [[75, 200], [200, 200]], 'FG-0203-6-S1', anno=[140, 200])
    s.opc('OPC-T02', [75, 200], 'FG2', 'start', 'TEST-01', 'A', rot=180)
    s.pair('OPC-T02', 'OPC-T01')
    s.bubble('PT-201', [150, 222])
    s.line('LPT', [[150, 200], [150, 217]], 'FG-0203-6-S1', style='Secondary Style')
    s.tee('LPT', 'FG2', True)
    s.connect('LPT', 'PT-201', 'end')
    s.tie('BL-AG', [210, 200], 'FG2', 'end') if False else None
    s.text(30, 60, 'TEST-02 验证图：跨图连接器与 TEST-01 配对。', CN, 'ML')
    return s


if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for f in (t01, t02):
        print('写出', f().dump(out))
