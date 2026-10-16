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

## 符号库（2026-10-16 追加）
| 现象 | 原因 | 处理 |
|---|---|---|
| 设备类符号画出来只有一个小点 | `sym` 的 `scale` 是绝对比例，替代样式默认比例；给了 0.5 就比默认小 40 倍 | 不写 `scale`，或写成 倍数 × 样式默认比例（`assets/plant_style_scales.json`） |
| Plant 库的设备样式（泵、换热器、罐）不能当普通块用？ | 能用：块里有几何，只是默认尺寸大（如 `Vessel Style` 高 300 mm）、比例要自己定 | 先 `find` 看尺寸，再按上条设 `scale` |
| 库里没有想要的符号 | Plant 库只有 PIP/ISA 通用符号 | 手工新增（`symbol_geom.py` 的 `DEFS`），不依赖项目样式，见 `references/symbol_library.md` |

## 普通图元模式与流水线（2026-10-16 追加）
| 现象 | 原因 | 处理 |
|---|---|---|
| Plant 智能对象路线 103 图随机崩溃（eNotOpenForWrite，dwgprops/syncstyles/regen 超时，newdwg AV） | `AssetAdder`/`LineSegmentAdder`/连接调用在本机不稳定；`PB_LINE_AUTO`、`PB_NOZZLE_AUTO`、`PB_CONN_ROWID` 三个开关对照实验均无效 | 改画普通图元（`plain_convert.py` + `build_set.ps1 -Plain`）：连续多轮整套一次成功 |
| 失败日志看不出现场 | 崩溃时 `<动词>.log` 不写出，旧版 `build_set` 复制的是上一张图的旧 `draw.log` | 现版留证 `<动词>.live.log` 到 `<Backup>\_故障留证\` |
| `Stop-Acad` 把用户自己的 AutoCAD 也杀了 | 旧版会强杀所有 AutoCAD | 现版只结束自启进程（`-All` 才处理全部）；`Start-Acad` 发现外来实例即抛异常停止（`PB_ALLOW_FOREIGN=1` 可跳过） |
| 启动后立刻发命令失败率高 | AutoCAD 刚打开项目时仍在后台加载 | `Start-Acad` 打开项目后默认等 30 s 并等 CPU 静默（`PB_SETTLE_SEC=0` 关闭） |
| 流水线 `draw` 后日志是空的、进程几秒就结束 | 用 `DETACHED_PROCESS` 启动 PowerShell 会丢掉输出 | 用 `CREATE_NO_WINDOW` + `CREATE_NEW_PROCESS_GROUP` 启动：父进程退出后子进程继续跑，日志完整 |
| JSON 里的路径出现 `Invalid \escape` | 反斜杠没转义 | `pipeline.json` 里的路径一律写正斜杠 |
| 在命令行里写 `\` 被折成单个 `\`，字符串替换失败或文件里出现控制字符 | 本工具环境对反斜杠的处理 | 含反斜杠的替换用 `chr(92)` 拼，或用编辑工具改文件，不用 heredoc 里的 Python |
| 子类重写 `S.line()` 后新增参数（`noarrow=True`）报 unexpected keyword | 项目的版面基类只透传固定参数 | 重写时加 `**extra` 并透传给 `super().line(...)` |
| `accoreconsole.exe` 无头打开 DWG 没有任何输出，进程挂起 | 本机该程序加载 Plant 环境后不回应脚本 | 不用它做核查；改查 spec 和 PDF。挂起的进程用任务管理器结束，不要批量杀 |
| 在二进制 DWG 里扫“GPT”等三字母词命中 | 压缩数据里的随机巧合 | 二进制扫描只用 5 个字符以上的词 |
| DWG 属性里“最后保存者”是 Windows 用户名 | AutoCAD 保存时自动写入，无法由脚本清除 | `plain_pipeline.py post` 会报告；对外发 DWG 时由用户决定（改发 PDF 或另存） |
| PDF 里抽不出文字 | 文字按曲线输出 | 位号和线号核对用 `check_plain.py` 对照 spec |
| 流向箭头压在符号或断口上 | 旧规则在每个拐角都放箭头 | 现规则：每条主管线只在末段放一个，与符号、断口重叠不放 |
| 管线沿器壁走、与设备边线重合 | 管嘴方向与管线来向不一致 | 管嘴 `rot` 与来向一致；上下串联设备同轴 |
| 用户的 AutoCAD 正在运行时启动引擎 | 旧版没有检查 | 现版 `draw` 先查有线程的 acad 进程，有则拒绝 |
| 删除命令被安全检查拒绝（带通配符的 `rm -f dir/*`） | 工具对批量删除保守 | 输出到新目录代替清空旧目录；确需删除的目录让用户确认 |
