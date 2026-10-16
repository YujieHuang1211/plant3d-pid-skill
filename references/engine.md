# PidBot 引擎与命令

## 普通图元模式（唯一路线，2026-10-16 起）
出图不创建 Plant 智能对象：Plant 的 `AssetAdder` / `LineSegmentAdder` / `ConnectLineWithAsset` 在本机会随机崩溃（`eNotOpenForWrite`，一次成功率约一半到三分之二），而验收看的是“规范合理的可编辑 DWG”，不是对象是否智能。

**一条龙：`scripts/plain_pipeline.py <_工作底稿> <子命令>`**（配置在 `_工作底稿/pipeline.json`，由 `new_project.py` 生成）
| 子命令 | 做什么 |
|---|---|
| `prep [图号…]` | 离线（数秒）：运行 `sheets.py` 生成 Plant 版 spec → `lint_specs.py` → `plain_convert.py` → 普通版 lint → `check_plain.py` → 预览 PNG（`预览/`）。任一步失败退出码 1 |
| `draw [图号…] [--redraw] [--wait]` | 先重跑检查；有线程的 acad 进程在运行则拒绝；写 `run_set.ps1`（带 BOM）后用 Windows PowerShell 5 后台启动；项目不存在先 `setup_project.ps1`，再 `build_set.ps1 -Plain`。日志 `_出图日志/`。已出过的图须加 `--redraw` |
| `status` | 最近一次出图日志的进度和结果 |
| `post` | PDF → PNG（`终审PNG/`）→ 清空 PDF 元数据 → 合并图集 → 扫描 PDF 元数据和 DWG 里的敏感词、报告 DWG“最后保存者” → 项目 zip 备份（`_恢复备份/`） |

`pipeline.json` 字段：`project`（项目名，也是标题栏项目名）、`parent`（Plant 项目父目录）、`layout`（版面模块）、`catalogs`（额外符号目录，相对工作底稿目录或绝对路径）、`stylecfg` / `schema` / `projprops`（建新项目用的配置，缺省用引擎默认）、`dwg`（图号→DWG 文件名，缺省“图号_图名.dwg”）、`ban`（额外禁用词）。路径一律用正斜杠。

**分步命令**（流水线内部调用，也可单独用）
```
python scripts\plain_convert.py <Plant 版 specs> <普通版输出目录> --catalog assets\symbol_catalog.json --catalog <项目目录.json> [图号…]
python scripts\check_plain.py <Plant 版 specs> <普通版 specs> [--ban 词1,词2]
powershell.exe -File …\build_set.ps1 -Project <Project.xml> -Specs <普通版目录> -Pdf <PDF目录> -Backup <zip目录> -Sheets "图号|图名.dwg;…" -Plain [-Redraw]
```
`-Plain` 时：跳过 `verify_topology` / `check_orphans`；`-Redraw` 默认同一会话接着画（没有 Plant 对象，不会因清理线组闪退），不做 `purge` 和连接器重配对。一张图约 27 s，整套 6 张约 350 s（含启动约 130 s）。

**`plain_convert.py` 补上原来由 Plant 自动生成的东西**
| 内容 | 做法 |
|---|---|
| 符号 | `asset`/`cv` → `sym`（控制阀 = 阀体块 + 执行机构块），在“符号”层 |
| 管线 | `poly`，线宽、颜色、线型只由图层决定（实体随层）：管线-主 0.70 红；管线-次 0.35 黄；信号-电 0.18 青 虚线；信号-软件 0.18 洋红；符号 0.35；位号 0.25 绿 |
| 断线 | 内联符号两端连接点处把管线断开；线交叉处打断较细的线（同级打断横线，每侧 1.4 mm）；T 形接头不处理 |
| 管嘴 | `nozzle` → 自器壁沿 `rot` 方向 3 mm 接管 + 一对法兰线（间距 1 mm，长 5.2 mm），符号层 |
| 流向箭头 | 每条 Primary 线只在末段放一个；末段上有朝向来流的管嘴时，箭头尖退到法兰外；与符号或断口重叠处不放；线上 `noarrow=True` 的不放 |
| 线号 | `group` 拼 `Service-LineNumber-NominalSize-NominalSpec`，标注点在线上时贴在线的上方（竖线贴左侧） |
| 位号 | 阀门椭圆；仪表圈（两行：类别/回路号）+ 到符号的细连线；设备位号带下划线 |
| 跨图连接器 | 左格字母、右格去向图号；去向全文放在连接器背向侧，碰到标题栏则翻到另一侧；竖向连接器图号旋转 90° |
| 其他 | 信号线（软件）中点小圆；`connect`、`tee`、`opc` 丢弃 |
引擎 `draw` 顶层支持 `"layers": [{"name","color","ltype","lw"}]`（`lw` 单位 0.01 mm）。
图例页符号要按目录外框自动算占行数和居中偏移，不要手写偏移：弹簧式安全阀外框偏上 2.1 mm，手写居中会顶出行框。管嘴图例用 3 条 `poly` 手画（见范例）。


---
以下为引擎通用说明。其中 Plant 智能对象相关内容（`asset`/`cv`/`line` 的 Plant 对象、`nozzle`/`connect`/`tee`/`opc`、`verify_topology`、`check_orphans`、`-Reopen`、重画两会话、环境变量、SDK 资料）**已停用，仅备查**：普通图元模式不会用到。
---

## 组成（`E:\05p_id图绘制中心\_PidBot`）
| 位置 | 内容 |
|---|---|
| `src\Core\*.cs` | 核心（.NET 8）。`dotnet build -c Release` 输出到 `bin\core\PidBot.Core.dll`，热加载，改代码不必重启 AutoCAD |
| `src\Loader` | 加载器 `bin\loader\PidBotLoader.dll`（NETLOAD 一次，按动词调用核心） |
| `scripts\pidbot.psm1` | 驱动模块：`Start-Acad`、`Invoke-PbVerb`、`Invoke-PbAnno`、`Get-AcadDialogs`、`Stop-Acad`、`Set-RecoveryMode` |
| `scripts\build_set.ps1` | 出图批处理（单会话 / 只重画 / 重开核对 / 恢复重试） |
| `scripts\setup_project.ps1` | 新建并配置 Plant 项目 |
| `scripts\send.ps1`、`acadctl.ps1` | 旧接口的薄封装（单条命令、对话框、退出） |
| `specs\qmz_*.json` | 项目配置：标签格式、类与属性、符号库（含自定义符号）、模板、项目属性 |
| `logs\<verb>.log`、`*.live.log` | 每个动词的结果与逐行进度；`draw_<图号>.log`、`verify_*.json`、`orphans_*.json` |
| `backup\` | 引擎源码与配置的备份 zip |

源码快照同时存于本技能 `assets/engine_src_snapshot.zip`。

## 动词（`Invoke-PbVerb <动词> <参数>`）
- **会话级**（PBS，可切换文档）：`newproject <json>`、`openproject <Project.xml>`、`newdwg <图名.dwg>`、`opendwg <图名.dwg>`、`rmdwg <图名.dwg>`（拒绝移除已打开的图）。
- **文档级**（PB）：
  - 出图流程：`dwgprops <props.json>`、`syncstyles <stylecfg>`、`draw <spec.json>`、`regen`、`qsave`、`pdf <输出.pdf>`；
  - 核对：`info`（导出对象、外框、连接点）、`conn`；
  - 项目配置：`purge`（删空线组）、`schema`、`stylecfg`、`tagformats`、`mkdwt`、`settemplate`、`projprops`；
  - 诊断：`stylesof`、`blockinfo`、`dwginfo`、`reflect`。
- 结果写 `logs\<verb>.log`。有“错误:”即失败；“Plant 对象状态异常”表示 fail-fast 终止，属偶发故障。

## spec 项（`draw` 的 JSON：`{"clear": false, "items": [...]}`）
| k | 字段 | 说明 |
|---|---|---|
| `line` | id, style, pts, group{Service,LineNumber,NominalSize,NominalSpec}, props, anno | 管线或信号线。同一 LineNumber 归入同一线组 |
| `asset` | id, style, at, rot, props, anno, auto | 符号。线外符号（仪表圈、PLC、联锁、设备、跨图连接器）`auto: true` 才会显示位号或文字 |
| `cv` | id, body, act, at, props, anno | 控制阀（阀体 + 执行机构） |
| `nozzle` | id, on, at, rot, style | 设备管嘴 |
| `connect` | line, asset, ctx(start/end/inline) | 显式建立连接，自动化不会替你连 |
| `tee` | line, to, start | 线端接到另一条线 |
| `opc` | a, b | 跨图连接器配对（ConnectorsRelationship），对方图纸不必打开 |
| `text` / `table` / `sym` | at, … | 普通文字、表格、图例符号块（不是 Plant 对象） |
- 每个 spec 的 id 与行号对照写入 `<spec>.ids.json`；解析 id 时载入同目录全部 `*.ids.json`。
- 标注写入 `<spec>.anno.lsp`，由驱动在命令外逐条执行（`_PIDANNOTATE … "_non" "x,y"`）。

## build_set.ps1
```
build_set.ps1 -Project <Project.xml> -Specs <specs目录> -Pdf <PDF目录> -Backup <zip目录>
              -Sheets "P&ID-101|P&ID-101_xxx.dwg;P&ID-102|…"
              [-Session single|per-sheet] [-Redraw] [-Reopen] [-Tools <本技能 scripts>]
```
- **开始前**：先 lint，0 ERROR 才启动 AutoCAD。备份“出图前”zip（排除 `*.dwl*` 锁文件，附带 `*.ids.json`）。
- **单会话（默认）**：AutoCAD 只启动一次。每张图依次执行 newdwg → dwgprops → syncstyles → draw → 标注 → regen → qsave → pdf，图纸不关闭；每张通过后打一个 zip。
- **故障处理**：
  - Plant 状态异常、对话框、超时或 AutoCAD 退出：失败现场改名留证 → 用最近 zip 恢复 → 新会话从该图起重试一次；
  - spec 错误：立即停止。
  - 每次故障把 `<动词>.live.log`、`draw.live.log`、`newdwg.live.log` 带时间戳存到 `<Backup>\_故障留证\`（2026-10-16 起）。崩溃时 `<动词>.log` 不会写出，只有 live 日志有现场；此前版本复制的是上一张图的旧 `draw.log`，不能用来定位。
- **结束时**：退出 AutoCAD → `verify_topology.py`（全部已出图纸）→ `check_orphans.py`，两项都须 PASS。
- **`-Redraw`**：
  1. rmdwg 要重画的图，删除它们的 id 登记，purge 空线组；
  2. 默认 `-RedrawSession two`：移除与清理一个会话，重画另开一个会话，多一次约 140 s 的启动，但稳妥。`one` 同一会话接着重画，基准项目两次通过；但正式项目一次重画 4 张、清理 48 个线组后，画到第 3 张闪退过一次。所以 `one` 只用于一两张的小改动；
  3. `repair_opc.py` 从其他图的 spec 中挑出引用被重画图的连接器配对，重新配对；
  4. 核查全部图纸、查残留、备份“重画后”zip。
  - 重画中途发生偶发故障时：用最近 zip 恢复，对尚未重画的图重新移除并清理，再重试。
- **`-Reopen`**：全新会话逐张 opendwg + info，`reopen_check.py` 核对位号。

## 会话规则（违反即闪退或吞命令）
- PidBot 命令内部不关闭文档；每个动词开始时重设 WorkingDatabase。
- 同一会话内反复清图重画会 eNotOpenForWrite。所以重画都走新会话，或者 `-Redraw`。
- 连接前不要查询关系（`dlm.GetRelatedRowIds`），否则下一次连接会 eNotOpenForWrite。
- 每张图都要 syncstyles，因为模板不含样式。
- 退出常卡死，需要强制结束。批量期间 `RECOVERYMODE=1`，结束后 `Set-RecoveryMode 2`。
- 会话级命令（newdwg 等）结束后 AutoCAD 不会自行回到空闲，驱动发 ESC 收尾，不要等满超时。

## 典型耗时（9 张 A3，本机实测 2026-10-07）
| 环节 | 旧流程 | 现流程 |
|---|---|---|
| AutoCAD 启动 | 每张 1 次 | 每批 1 次。启动到可自动化约 110~150 s，是固定成本，与是否记忆上次项目无关 |
| 全套 9 张（含核查与备份） | 1725~2676 s | 466 s（含启动 151 s）；加重开核对 692 s |
| 单张出图（会话内） | 2.5~5.5 min | 26~52 s（标注多的图慢一些，每条标注约 0.6 s） |
| 改一张图 | 从该张起整串重画，30~45 min | `-Redraw`（两会话）约 6.5 min；`-RedrawSession one` 约 4 min |
| 新建并配置 Plant 项目 | 约 10 min | 约 180 s |
| 版面检查 | 出 PDF 后人工看 | lint + 预览，9 张约 1 s |

## 排查用环境变量（2026-10-16，默认值即原行为）
在启动 AutoCAD 的 PowerShell 会话里设置，仅影响 `draw`：
| 变量 | 取值 | 作用 |
|---|---|---|
| `PB_LINE_AUTO` | `0` / `1`（默认 1） | `LineSegmentAdder` 的 enableAutomations |
| `PB_NOZZLE_AUTO` | `0` / `1`（默认 1） | 管嘴 `AssetAdder` 的 enableAutomations |
| `PB_CONN_ROWID` | `1` 启用（默认 0） | 线–对象连接改用官方示例的行号重载，不套自建事务 |

## 官方资料（Plant 3D SDK）
- 安装包放在 `E:\Users\yujie\Downloads\AutoCAD Plant 3D 2026 SDK`：`docs\plantsdk_ref.chm`、`plantsdk_dev.chm`（API 参考）；`samples\PnID\PnIDCreateSline\DrawPnID.cs`（官方建资产、管线、管嘴、内联阀并连接的示例）、`PnPScanValves`、`ListPipelineObjects`。
- 公开参考：`autodesk-platform-services/skills` 仓库 `skills/acad-dotnet/references/plant3d-api.md`（API 世界地图、DataLinksManager、关系表、`AssetAdder`/`LineSegmentAdder` 用法）。官方文档只说明“所有 Plant API 只能在 AutoCAD 主线程调用”，没有 `eNotOpenForWrite` 的说明。
- 遇到不确定的 API 行为先查这两处，再在验证项目试，不要凭印象写。
