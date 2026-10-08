"""新项目 P&ID 工作目录脚手架：建 `<阶段目录>/_工作底稿/`，写入模型模板与版面模块模板，并打印后续命令。
用法: python new_project.py <阶段目录，如 …/05_P&ID工艺流程图绘制> <项目名> [Plant 项目父目录，默认 E:\\05p_id图绘制中心]
已存在的文件不覆盖。
"""
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ENGINE = Path(r'E:\05p_id图绘制中心\_PidBot')

MODEL = {
    'meta': {'project': '', 'doc': 'P&ID 设计模型', 'rev': 'R0', 'date': '', 'status': '',
             'basis': [], 'basis_doc': [], 'source_codes': {'C': '甲方输入', 'U': '设计确认', 'E': '工程假设/推荐（待验证）'},
             'ce_notes': [], 'safety_rules': [], 'pending_note': ''},
    'conventions': {'fluids': {}, 'pipe_classes': {}, 'action_columns': [], 'mode_columns': [], 'effect_columns': [], 'wbs_per_unit': {}},
    'boundary': [], 'equipment': [], 'inline': [], 'tees': [], 'lines': [], 'instruments': [], 'signals': [],
    'interlocks': [], 'modes': [], 'open_points': [],
    'sheets': [{'no': 'P&ID-000', 'title': '封面与图纸目录'}, {'no': 'P&ID-001', 'title': '图例与符号说明'},
               {'no': 'P&ID-101', 'title': ''}],
    'review_log': [],
}

LAYOUT = '''"""{name} P&ID 版面（坐标 mm，A3 模型空间；可绘区 x 25~415、y 5~292；x>235、y<91 为标题栏禁区）。
用法: python sheets.py <specs 目录> [图号 …]
参照技能 assets/example/ 的青木子项目版面；连接点用 attach() 取，出图前跑 lint_specs.py 与 preview_spec.py。
"""
import sys
from pathlib import Path

sys.path.append(r'{scripts}')
from pidlib import *  # noqa: E402,F401

use_model(Path(__file__).resolve().parent / 'pid_model.json')


def sheet_101():
    s = Sheet('P&ID-101')
    # 例：s.line('L1', [[50, 268], [360, 268]], 'H2-0101-6-S1', anno=[285, 268])
    #     s.hand('HV-101', [64, 268], 'L1', anno=oval(64, 257))
    return s


SHEETS = {{'P&ID-101': sheet_101}}

if __name__ == '__main__':
    build(SHEETS, sys.argv[1], sys.argv[2:] or None)
'''


def main(stage, name, parent=r'E:\05p_id图绘制中心'):
    w = Path(stage) / '_工作底稿'
    w.mkdir(parents=True, exist_ok=True)
    (w / '备份').mkdir(exist_ok=True)
    m = w / 'pid_model.json'
    if not m.exists():
        model = json.loads(json.dumps(MODEL))
        model['meta']['project'] = name
        m.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding='utf-8')
        print('写出', m)
    lay = w / 'sheets.py'
    if not lay.exists():
        lay.write_text(LAYOUT.format(name=name, scripts=SKILL / 'scripts'), encoding='utf-8')
        print('写出', lay)
    pp = w / 'projprops.json'
    if not pp.exists():
        pp.write_text(json.dumps({'Project_Description': f'{name} P&ID', 'Project_Number': '待定',
                                  'Client_Information_Company_Name': '', 'Project_Data_DesignOrg': ' '}, ensure_ascii=False, indent=1), encoding='utf-8')
        print('写出', pp)
    specs = ENGINE / 'specs' / name
    sc = SKILL / 'scripts'
    print(f'''
下一步：
1. 填 pid_model.json（字段见 references/model_schema.md），用 make_review.py 出设计依据表请用户确认：
   python "{sc}\\make_review.py" "{m}" "{stage}\\P&ID设计依据与连接关系表_R0（待确认）.xlsx"
2. 新建 Plant 项目（约 4 min）：
   powershell -File "{ENGINE}\\scripts\\setup_project.ps1" -Name "{name}" -Parent "{parent}" -ProjProps "{pp}"
3. 写 sheets.py，生成 spec，检查与预览：
   python "{lay}" "{specs}"
   python "{sc}\\lint_specs.py" "{specs}" P&ID-101 …
   python "{sc}\\preview_spec.py" "{specs}" "{w}\\预览" P&ID-101 …
4. 出图（后台运行；同时生成 Office 交付件）：
   powershell -File "{ENGINE}\\scripts\\build_set.ps1" -Project "{parent}\\{name}\\Project.xml" -Specs "{specs}" -Pdf "{parent}\\{name}\\出图PDF" -Backup "{parent}\\_备份" -Sheets "P&ID-101|P&ID-101_图名.dwg;…" -Reopen
''')


if __name__ == '__main__':
    main(*sys.argv[1:4])
