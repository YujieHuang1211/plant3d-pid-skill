"""由 pid_model.json 生成《P&ID 设计依据与连接关系表》xlsx（供用户确认连接关系后再绘图）。
用法: python make_review.py <pid_model.json> <输出.xlsx>
"""
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import colconv  # noqa: E402

M = {}

FONT = Font(name='宋体', size=10)
BOLD = Font(name='宋体', size=10, bold=True)
TITLE = Font(name='宋体', size=14, bold=True)
THIN = Side(style='thin', color='000000')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD = PatternFill('solid', fgColor='D9D9D9')
WRAP = Alignment(wrap_text=True, vertical='center')
CENTER = Alignment(wrap_text=True, vertical='center', horizontal='center')


def sheet(wb, name, headers, rows, widths, title=None):
    if not rows:            # 没有内容的表不建（模板里的空表头页没有用）
        return None
    ws = wb.create_sheet(name)
    r0 = 1
    if title:
        ws.cell(1, 1, title).font = TITLE
        r0 = 3
    for j, h in enumerate(headers, 1):
        c = ws.cell(r0, j, h)
        c.font, c.fill, c.border, c.alignment = BOLD, HEAD, BOX, CENTER
    for i, row in enumerate(rows, r0 + 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(i, j, v)
            c.font, c.border, c.alignment = FONT, BOX, WRAP
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f'{r0}:{r0}'
    return ws


def main(model, out):
    M.update(json.loads(Path(model).read_text(encoding='utf-8')))
    wb = Workbook()
    ws = wb.active
    ws.title = '说明'
    meta = M['meta']
    CV = M.get('conventions', {})
    lines = [
        ('文件', 'P&ID 设计依据与连接关系表（供确认，确认后据此绘制 Plant 3D P&ID）'),
        ('项目', meta['project']),
        ('版次/日期', f"{meta['rev']} / {meta['date']}"),
        ('状态', meta['status']),
        ('设计依据', '\n'.join(meta['basis'])),
        ('依据类别代号', '；'.join(f'{k}={v}' for k, v in meta['source_codes'].items()) + '；src 中的 R 加数字为技术方案版次，其后为章节或表号'),
        ('管线号规则', CV.get('line_number', '')),
        ('仪表位号规则', CV.get('tags', {}).get('instrument', '')),
        ('其他位号', '；'.join(f'{k}: {v}' for k, v in CV.get('tags', {}).items() if k != 'instrument')),
        ('管道等级', '；'.join(f'{k}: {v}' for k, v in CV.get('pipe_class', {}).items())),
        ('物料代号', '；'.join(f'{k}={v}' for k, v in CV.get('fluid_codes', {}).items())),
        ('图纸', '；'.join(f"{s['no']} {s['title']}" for s in M['sheets'])),
    ]
    ws.cell(1, 1, meta['project'] + ' P&ID 设计依据与连接关系表').font = TITLE
    for i, (k, v) in enumerate(lines, 3):
        a, b = ws.cell(i, 1, k), ws.cell(i, 2, v)
        a.font, b.font = BOLD, FONT
        a.border = b.border = BOX
        a.alignment, b.alignment = CENTER, WRAP
    ws.column_dimensions['A'].width, ws.column_dimensions['B'].width = 16, 120

    sheet(wb, '界区接口', ['编号', '方向', '内容', '条件', '供方', '依据'],
          [[b['id'], '进' if b['dir'] == 'in' else '出', b['desc'], b['cond'], b['by'], b['src']] for b in M['boundary']],
          [10, 6, 40, 46, 10, 12])

    sheet(wb, '连接关系', ['管线号', '介质', '起点', '依次经过（流向）', '终点', '操作条件', '流量', '备注'],
          [[l['no'], M['conventions']['fluid_codes'].get(l['fluid'], l['fluid']), l['seq'][0], ' → '.join(l['seq'][1:-1]), l['seq'][-1],
            l.get('op', ''), l.get('flow', ''), l.get('note', '')] for l in M['lines']],
          [16, 14, 12, 60, 18, 22, 18, 30])

    sheet(wb, '三通与分支', ['编号', '所在管线', '分支', '说明'],
          [[t['id'], t['on'], t['branch'], t.get('desc', '')] for t in M['tees']], [10, 18, 18, 50])

    sheet(wb, '设备', ['位号', 'Plant 类', '符号', '名称', '规格', '供方', '依据'],
          [[e['tag'], e['class'], e['symbol'], e['name'], e['spec'], e['by'], e['src']] for e in M['equipment']],
          [10, 16, 18, 18, 70, 18, 14])

    sheet(wb, '阀门管件与在线仪表', ['位号', '类型', '说明', '规格', '故障位置', '依据'],
          [[x['tag'], x['type'], x['desc'], x.get('spec', ''), x.get('fail', ''), x['src']] for x in M['inline']],
          [10, 14, 34, 60, 8, 22])

    loc = {'field': '现场', 'field_integral': '现场（一体）', 'plc': 'PLC/HMI', 'vendor': '设备自带'}
    sheet(wb, '仪表与点位', ['位号', '位置', '功能', '量程', '设定值', 'I/O', '依据'],
          [[x['tag'], loc.get(x['loc'], x['loc']), x['desc'], x.get('range', ''), x.get('setpoint', x.get('alarms', '')), x.get('io', ''), x['src']]
           for x in M['instruments']],
          [10, 10, 40, 14, 34, 22, 24])

    typ = {'software': '软件/通信', 'electric': '电信号', 'pneumatic': '气动'}
    sheet(wb, '信号', ['起', '止', '类型', '说明'],
          [[s['from'], s['to'], typ.get(s['type'], s['type']), s.get('desc', '')] for s in M['signals']], [22, 30, 12, 60])

    acols = colconv.action_columns(M)
    sheet(wb, '联锁因果表', ['编号', '原因', '检测', '设定值'] + [a[1] for a in acols] + ['复位', '依据'],
          [[i['id'], i['cause'], i['detect'], i['setpoint']] + [i['actions'].get(a[0], '') for a in acols] + [i['reset'], i['src']]
           for i in M['interlocks']],
          [7, 28, 20, 26] + [16] * len(acols) + [20, 18])
    mcols = colconv.mode_columns(M)
    if M['modes']:
        sheet(wb, '运行工况', ['编号', '工况'] + [c[1] for c in mcols],
              [[m['id'], m['name']] + [m.get(c[0], '') for c in mcols] for m in M['modes']],
              [6, 24] + [22] * len(mcols))

    if M.get('symbols'):
        sheet(wb, '符号对应表', ['对象类别', 'Plant 类', '采用符号（样式）', '来源', 'A3 打印尺寸', '注'], [list(r) for r in M['symbols']],
              [26, 34, 40, 26, 14, 30], title='对象类别—采用符号—来源')

    sheet(wb, '待确认', ['编号', '事项', '原因', '建议'],
          [[q['id'], q['item'], q['why'], q['proposal']] for q in M['open_points']], [7, 40, 50, 40])

    wb.properties.creator = ''
    wb.properties.lastModifiedBy = ''
    wb.save(out)
    print('saved', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
