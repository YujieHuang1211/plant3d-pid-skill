# PidBot 引擎与命令

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
