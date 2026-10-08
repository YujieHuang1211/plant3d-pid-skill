# pid_model.json 结构

项目的唯一数据源，版面模块、联锁/工况表、清单、设计依据表都从它生成。完整示例：`assets/example/pid_model.json`（青木子纽扣电池测试台）。

## 依据标注（每个对象的 `src`）
- `C` 甲方输入，`U` 或“设计确认”为已确认的设计决定，`E` 或“工程推荐/工程假设”为本阶段提出、待验证的内容。也可以写来源文件与条目，例如 `R8 表4`、`R1 02.05`。
- `src` 进入图上对象的 BasisRef 属性和清单的“依据”列：写给读图人看，不写工具名、审查者名、聊天用语。
- 带 `R1 xx.yy` 的条目由 `export_lists.py` 与成本询价表按 WBS 对账；一个询价行在图上对应多个对象时，在 `PER_UNIT` 中说明。

## 顶层字段
| 字段 | 内容 |
|---|---|
| `meta` | project, doc, rev, date, status, basis[]（内部依据，可含路径）, basis_doc[]（对外依据，只写文件名称）, source_codes；可选 ce_notes[], safety_rules[], scope_text, pending_note |
| `conventions` | 物料代号、管道等级；可选 action_columns, mode_columns, effect_columns（联锁/工况表的列） |
| `boundary[]` | id(BL-xx), dir(in/out), desc, cond, by(甲方/我方), src：界区接口 |
| `equipment[]` | tag(F-301…), class, symbol, name, spec, by, src |
| `inline[]` | tag, type(ball_valve/needle_valve/check_valve/filter/regulator/on_off_valve/mfc/cap/flow_switch), desc, spec, src；可选 normally:"NC", fail:"FC"/"FO" |
| `tees[]` | 三通位置说明（供审阅） |
| `lines[]` | no（物料-主项序号-外径-等级，如 H2-0101-6-S1）, fluid, seq[]（沿流向的对象序列，`xx:start` 表示接到另一条线）, op, flow |
| `instruments[]` | tag(ISA 字母+回路号), loc(field/plc/…), desc, range, setpoint, alarms, io（控制点位，如 DO01、AI01、COM03）, on（所在对象）, src |
| `signals[]` | 信号连接（供审阅） |
| `interlocks[]` | id(I-xx), cause, detect, setpoint, actions{动作键: 文字}, reset, src；推荐 effects[]（触发的矩阵列） |
| `modes[]` | id(M0…), name, 各状态键（与 mode_columns 对应）, permissive, exit |
| `open_points[]` | id(Q-xx), item, why, proposal, resolution（决定后填写，写明确认日期） |
| `sheets[]` | no(P&ID-xxx), title, content：顺序即图纸顺序，决定标题栏“第 N 张/共 M 张” |
| `review_log[]` | 内部修改记录（不进交付件） |

## 编号约定（HG/T 20519 + ISA-5.1）
- 管线号：`物料代号-主项序号-外径(mm)-管道等级`。主项百位 01 配气、02 混气/旁路、03 炉/尾气……按项目定义。
- 仪表位号：ISA 字母代号 + 回路号（FIC-101、XV-101、PT-201、TIC-301、AIT-401、HS-401）。回路号百位与主项对应。
- 设备：F 炉、X 夹具或试验件、JL 电子负载、V 容器、E 换热器……。手阀 HV、止回阀 CK、过滤器 FL、界区接口 TP。
- 联锁 I-01…，工况 M0…，待定 Q-01…。

## 版面模块（每个项目一个或几个 .py）
```python
import sys; sys.path.append(r'C:\Users\yujie\.claude\skills\plant3d-pid\scripts')
from pidlib import *
use_model(r'..\_工作底稿\pid_model.json')

def sheet_101():
    s = Sheet('P&ID-101')
    s.line('LH2', [[50, 268], [360, 268]], 'H2-0101-6-S1', anno=[285, 268])
    s.tie('BL-H2', [40, 268], 'LH2', 'start', label='H₂ 气源（甲方一级减压后）', label_at=[30, 274.5])
    s.hand('HV-101', [64, 268], 'LH2', anno=oval(64, 257))
    s.bubble('PT-201', [150, 162]); s.ilock('I-02', [250, 162])
    s.sigc('S1', [attach('Field Mounted Discrete Instrument Style', [150, 162], 'R'),
                  attach('Primary Loc Accessible PLC Style', [250, 162], 'L')], 'Electrical Style', 'PT-201', 'I-02')
    return s

if __name__ == '__main__':
    build({'P&ID-101': sheet_101}, sys.argv[1])
```
`pidlib.Sheet` 的方法：
- 管线与信号：`line`、`sigc`、`sig`、`tee`、`connect`；
- 线上对象：`hand`、`special`、`inst_inline`、`xv`、`pcv`；
- 线外符号与设备：`bubble`、`plc`、`ilock`、`equip`、`nozzle`、`tie`；
- 跨图连接器：`opc`、`pair`；
- 文字与表格：`text`；`table()`、`wrap()`。

示例项目的全部版面见 `assets/example/`。
