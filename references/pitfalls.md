# 故障与教训（AutoCAD Plant 3D 2026 简中，PidBot 自动出图）

每条按“现象 → 原因 → 已采取的处理”记录。新问题照此格式补充，并在验证项目复现、修复后再用于正式项目。

## 闪退与 Plant 状态异常
| 现象 | 原因 | 处理 |
|---|---|---|
| 致命错误 AV 0x0008（关闭文档后） | 文档关闭后 WorkingDatabase 失效 | 命令内不关闭文档；每个动词开始时重设 WorkingDatabase；改模板、符号库后恢复为活动文档的数据库 |
| `eNotOpenForWrite` 闪退（同会话反复清图重画） | 同一会话里删除并重建大量 Plant 对象 | 每次重画都开新会话或用 `-Redraw`；不在绘图会话里做全项目清理 |
| `eNotOpenForWrite` 闪退（连接时） | 连接前调用 `dlm.GetRelatedRowIds` 查重 | 已撤销查重。连接前不要查询关系 |
| `eWasOpenForRead` / `eHadMultipleReaders` | 连接调用遗留读者；偶发 | 每次连接用独立事务；出现即 fail-fast 终止。`build_set` 留证后恢复 zip，在新会话重试 |
| 改 schema 后同会话首次绘图闪退 | 元数据变更未在新会话生效 | 项目配置与绘图分开会话（`setup_project` 结束即退出） |
| `eNotOpenForWrite` 闪退（同会话 rmdwg 4 张 + purge 48 个线组后接着重画，第 3 张时） | 大量删除后在同一会话继续建对象 | `-Redraw` 默认两个会话（`-RedrawSession two`）。`one` 只适合重画一两张的小改动 |
| 闪退后弹“AutoCAD 错误中断”，脚本等满 10 min 超时才恢复 | 进程还在，命令不会完成 | 驱动每 3 s 查一次致命错误对话框，发现即按偶发故障恢复 |
| 符号库保存时“保存过程中发生错误” | 新建自定义样式时 WorkingDatabase 没指向符号库侧库 | 编辑侧库期间切换 WorkingDatabase；保存后重读核对样式数 |

## 数据残留（位号带“?”）
| 现象 | 原因 | 处理 |
|---|---|---|
| 重画后线组位号“0101?” | rmdwg 不删线组，旧空线组还在 | `-Redraw` 在独立会话中 purge 空线组；`check_orphans.py` 检查 |
| 重画后设备/阀门位号带“?” | 闪退前已登记的位号（对象已不存在） | 不改库；用闪退前的 zip 恢复。`check_orphans.py` 能查出孤立登记 |

## 启动与命令被吞
| 现象 | 原因 | 处理 |
|---|---|---|
| 启动后停在开始页，COM `Documents.Add` 无效 | 开始选项卡状态 | 启动参数 `/t <模板>` 直接建图；仍无文档就强制结束重启一次 |
| 强制结束后下次启动弹“图形修复”面板，吞命令 | 恢复机制 | 批量期间 `RECOVERYMODE=1`，启动时自动关闭面板；结束后恢复为 2 |
| newdwg 后命令长时间不返回 | 会话级命令后 AutoCAD 不回到空闲 | 日志写出即完成，驱动发 ESC，最多等 15 s |
| 每张图重启 AutoCAD 太慢 | 每张一个会话 | 默认单会话出全套 |
| 启动时间波动大（连续启动约 110~150 s，闲置一段时间后首次约 250 s） | AutoCAD/Plant 自身加载，与是否记忆上次项目无关 | 不可控的固定成本：尽量少开会话，出图与核对一批完成 |

## 显示与版面
| 现象 | 原因 | 处理 |
|---|---|---|
| 线看似未连上，差 1~4 mm | 线端坐标手算，没落在符号连接点 | 用 `attach()`；lint 按符号目录报 ERROR |
| 跨图连接器 A/B 和去向文字为空 | 关闭自动化放置时文字不绑定属性 | 连接器用 `auto: true` 放置，**并且**显式 connect（自动化不会建连接） |
| 线外仪表、PLC、联锁、设备不显示位号 | 关闭自动化 | 线外符号一律 `auto: true` |
| 位号被吸走 | PIDANNOTATE 的点受运行中对象捕捉影响 | 点前加 `"_non"` |
| 标注样式取错（Insulation、DCS 显示） | PIDANNOTATE 不指定样式时取列表第一个 | 显式给样式：Pipeline Tag、Oval Tag Style、Field Mounted Discrete Instrument Style、Equipment Tag |
| PIP “Undefined Interlock Logic” 没有位号 | 该类无位号 | 软件联锁用 PLC 符号（方框内菱形），硬件联锁用硬件联锁菱形 |
| “CO” 印成 “C□” | PIP 标注块文字样式是 txt.shx（大写 O 为矩形） | 模板与符号库的非国标 SHX 样式统一改为 gbenor+gbcbig |
| 修订栏、标题栏被压 | 文字或表格超过可用高度 | 修订栏 3 行，顶边 89 mm；表格拆张；lint 检查 |
| 图例大符号越格，执行机构压上一行 | 块尺寸大；插入点在底部 | `SYMFIT` 设缩放、行数、竖向偏移 |
| 标题栏字段显示占位符 | 字段值为空 | 未定项写“—”；设计单位写一个空格 |

## 环境
- Windows PowerShell 5 脚本须带 UTF-8 BOM，否则中文路径和字符串会乱码。
- PowerShell 把中文弯引号 “ ” 当作字符串定界符，含这类引号的文本替换改用 Python 或编辑工具完成。
- 根目录不要含 `&`，已改为 `E:\05p_id图绘制中心`。
- Plant 项目放本地盘（SQLite 加文件锁），不放云盘；交付件放项目文件夹。
- 同一项目只开一个 AutoCAD，不并行写库。

## 运行环境与脚本编写（2026-10-16 追加）
| 现象 | 原因 | 处理 |
|---|---|---|
| “AutoCAD 启动超时”，停在开始页 | 用 PowerShell 7（pwsh）运行了引擎脚本：.NET Core 没有 `Marshal.GetActiveObject`，取不到 AutoCAD 对象 | 引擎脚本一律用 `powershell.exe`（Windows PowerShell 5） |
| 自写的 `.ps1` 一启动就报“找不到 …\setup_project.ps1”，路径是乱码 | 脚本含中文路径但存成不带 BOM 的 UTF-8，PowerShell 5 按 GBK 读 | 含中文的 `.ps1` 必须存为 UTF-8 **带 BOM**（引擎自带脚本都带 BOM）；写完用 `head -c3 \| xxd` 核对是 `efbbbf` |
| 后台任务启动后看似在跑，其实几秒前就失败了 | 启动后没有核对日志 | 后台启动后 30～60 s 内必须看到日志里出现第一条进度行（如“启动 AutoCAD”“=== P&ID-xxx”）才算启动成功，再向用户报预计耗时 |
| `build_set` 打包 zip 时报 IOException，文件被占用 | `-Backup` 目录放在项目文件夹里，zip 把自己也打进去 | 备份目录放项目外，例如 `_验证\_备份\<项目名>` |
| 验证 `verify_set` 报“位号不符”“缺关系/缺三通”，同一线号被别的图的线占用 | Plant 线组按线序号并组，**spec 里的线 id 必须在整套图内唯一**；两张图都叫 `LSMP` 就会串组 | 线 id 全套唯一；出图前用脚本核对所有 spec 的 line id 无重复 |
| 进程列表里有 acad.exe 但没有窗口、没有线程 | 僵尸进程（上次强制结束残留），不能被杀 | 判断 AutoCAD 是否在运行时，只算 `Threads.Count -gt 0` 的进程（`Get-Process acad` 已按此过滤） |
| 连接器 OPC 方向反、位置错 | `end` 型 rot=θ 体沿 θ 方向、插入点在尾；`start` 型箭头尖在管线起点，方向须与流向一致 | 管线向左流的进口连接器手写：`at=[x起点+OPC_LEN, y], rot=180`，再 `connect ctx='start'` |
| 竖向阀门位号竖排旋转 | 位号是 Plant 自动标注，随阀门方向旋转 | 接受；不要用手工文字替代自动位号 |
