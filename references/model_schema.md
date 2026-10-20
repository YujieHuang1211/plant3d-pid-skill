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

## 补充（2026-10-16）
- `meta.rev`：版次（如 R0、R1），写进封面、目录和每张标题栏的“版次”；`meta.rev_note`：修订栏“修订说明”（缺省“首版，供审查”）；`meta.date`：发布日期。版次递增时三项同步改。
- 版面模块里 `S.line(..., noarrow=True)`：该线不放流向箭头（设备内部连线用）。`S.nozzle(owner, id, at, rot)`：设备管嘴，`at` 在器壁上，`rot` 为向外方向；管线端点落在 `at` 上，或管线穿过它进入设备内部。
- 仪表条目的 `src` 为“工程假设”且无联锁、无操作用途的，出图前删掉（见 SKILL.md “仪表精简原则”），并同步模型、版面、联锁表。

## 补充（2026-10-20）：核对与编号相关的可选字段
都是可选字段，旧模型不写照常通过。
- 对象（equipment / inline / instruments / boundary / interlocks）：
  - `sheet`：该对象应画在哪张图。写了就核对（`validate_views.py`），没写只核对“整套图里有主表示”。
  - `omitted`：有意不画时写原因（如“炉自带热偶，随 TIC-301 注释表示”）。有这个字段才不报“没有主表示”。
- `signals[].kind`：`electric` / `pneumatic` / `data`。线型由信号含义决定：电信号虚线、气动信号带双斜线、通信/数据链路长划线（ISA-5.1-2024 表 10）。版面里用 `Sheet.signal(lid, pts, kind, a, b)`。
- `loops[]`：`{id, measure, control, final, signal}`，测量、控制功能、最终元件的位号。`check_numbering.py` 核对三者都在模型里；主图简化某个回路时在图注里引用典型回路详图。
- `retired`：`{line_seq: ["0103"], interlocks: ["I-02"], tags: ["PT-105"]}`，修订中作废的编号。stable 模式下缺号只提示，登记后不再提示；作废位号仍出现在旧注释里时不报“不在模型里”。
- `conventions.tag_pattern`：位号正则，缺省 `[A-Z]{1,4}-\d{3}[A-Z]?`（需要连字符）。项目用 `V101` 这类写法时写 `[A-Z]{1,4}-?\d{3}[A-Z]?`。
- 同一物理对象只定义一次、只有一个主表示。局部详图/第二张图要再画出来时，spec 里用另一个 id 加 `ref_of: "<位号>"`（如 `PT-102@103`），它不参与全套唯一和位号文字检查；`validate_views.py` 检查被引用对象有主表示。
- spec `nozzle` 的 `conn`：`flange` / `weld` / `thread` / `none`；不写则按制图配置（`pip-ref-a3` 为简单接管，不默认加法兰；`legacy-2026-10` 加一对法兰线）。

## 制图配置与编号模式
- `pipeline.json` 的 `profile`：`legacy-2026-10`（缺省，老项目图面不变）或 `pip-ref-a3`（`new_project.py` 对新项目写入）。数值与依据见 `assets/profiles/*.json`，图例线型行用 `pidlib.legend_rows(profile, used)` 生成。
- 编号模式随配置：`legacy` 为 continuous（每主项从 01 连续，联锁 I-01 连续），`pip-ref-a3` 为 stable（缺号只提示，重号报错）。
- 仪表精简（修订上述“仪表精简原则”）：依据是“工程假设”且没有联锁、操作用途的仪表，先列入 `open_points` 请用户确认，不因来源是工程假设就直接删；用户确认不要后才删，并同步模型、版面、联锁表、设计依据表。
