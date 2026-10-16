---
name: plant3d-pid
description: Use when drawing, revising or checking P&IDs (管道及仪表流程图) as standard, editable DWG sheets with the AutoCAD Plant 3D engine (plain CAD entities, no smart objects) for custom equipment or test-bench projects — a new P&ID set from a project folder (requirements, technical scheme, cost workbook), layout or connection fixes on existing sheets, interlock C&E or operating-mode tables, equipment/line/instrument lists — or when the drawing engine crashes (eNotOpenForWrite), hangs at startup, or sheets show unconnected lines, overlapping text or missing nozzles.
---

# P&ID 出图（普通图元 DWG）

## 概述
图纸只用普通 CAD 图元：符号块、多段线、文字、表格，**不创建 Plant 智能对象**（2026-10-16 用户定）。原因：智能对象路线在本机会随机崩溃，而验收看的是“规范、可编辑的 DWG 和 PDF”，不是对象是否智能。出图快（6 张 A3 约 6 min，含启动）、出错少，规范靠图层、线宽、打断、管嘴和流向箭头做到位。

数据流：
`pid_model.json`（工艺对象、连接、联锁、工况的唯一数据源）→ 版面模块 `sheets.py` 生成 spec → `plain_pipeline.py prep`（离线：lint、转成普通图元、内容核查、预览）→ `draw`（一个 AutoCAD 会话批量出图）→ `post`（PDF 转 PNG、清元数据、合并图集、扫描、备份）→ 人工逐张看 → 交付。

AutoCAD 只负责最终出图；版面、连接几何、压框、重叠都在离线检查和预览里解决。引擎是 `E:\05p_id图绘制中心\_PidBot`（C# 热加载插件 + PowerShell 驱动，源码快照见 `assets/engine_src_snapshot.zip`）。

## 何时用 / 不用
- 用：依据项目文件夹的需求、技术方案、成本表新出一套 P&ID；改已有图纸的版面或属性；出联锁因果表、运行工况、设备/管线/仪表清单；排查出图故障。
- 不用：只要一张示意流程图、不要图框和标准图层时，直接用 draw.io。

## 工作流（每个 ★ 是用户确认关口）
1. 读项目文件夹：需求、技术方案、成本表的询价表与控制点位表、补充资料。新版本优先于旧版本。
2. 写 `pid_model.json`，字段见 `references/model_schema.md`。每个对象写明依据：甲方输入、设计确认、工程假设。**仪表按“图面标准”一节的原则精简。**
3. ★ `make_review.py` 生成《设计依据与连接关系表》，请用户确认拓扑和待定点。
4. 定分图（A3 多张）和编号，写进 `sheets`。
5. `python scripts\new_project.py <阶段目录> <项目名>` 建 `_工作底稿/`（模型模板、`sheets.py`、`pipeline.json`、`projprops.json`）。
6. 写版面模块（`from pidlib import *`，参照 `assets/example/` 和 `references/layout_rules.md`）。
7. `python scripts\plain_pipeline.py <_工作底稿> prep`：版面 → lint → 转换 → 普通版 lint → `check_plain` → 预览 PNG（`预览/`）。全部 OK 才能出图；逐张看预览。
8. `plain_pipeline.py <…> draw --wait`（项目不存在时自动先建）。改动后重画加 `--redraw`，只重画列出的图：`draw P&ID-103 --redraw`。
9. `plain_pipeline.py <…> post`，**逐张看 `终审PNG/`**（截断、压框、重叠、线是否落在符号上、管嘴、标题栏字段）。有问题回到第 6 步。
10. ★ 版次递增时（R0→R1）：不覆盖旧版本，交付目录另放 `R1\`；`pid_model.json` 的 `meta.rev` 与 `meta.rev_note` 同步更新。一次复制到交付目录（项目在云盘时先本地生成自查）。
11. ★ 列出对上游文件（技术方案、成本表等）的影响，只列不改。

并行可做：`make_ce_modes.py`、`export_lists.py`（Office 交付件）。命令和参数见 `references/engine.md`。

## 图面标准（出图结果必须满足）
- **线宽层级（图层决定，实体一律随层，PDF 黑白也分得出）**：主工艺管线 0.70；仪表接管、取样、排凝支线 0.35；符号和管嘴 0.35；位号 0.25；电信号 0.18 虚线；软件/通讯线 0.18 实线加中点小圆。颜色：主管线红、次管线黄、电信号青、软件线洋红、位号绿，仅屏幕区分。
- **线断开**：内联符号（阀、过滤器、流量计）处线断开；两线交叉时断开较细的一条，同级断横线，每侧留 1.4 mm；T 接和端点相接不断。
- **设备管嘴**：设备上每个接管口画管嘴——自器壁沿 `rot` 方向伸出 3 mm 接管加一对法兰线；管线接在法兰外侧，流向箭头尖停在法兰外。管线穿过器壁到设备内部时，管嘴放在器壁上，壁内一段用 `noarrow=True` 的短线连到内部件。
- **流向箭头**：每条主管线只在末段放一个，不在每个拐角放。与符号、断口重叠处不放。
- **线号**：`物料代号-主项序号-外径-等级`，贴在线的上方（竖线贴左侧），不压符号、位号、设备。
- **位号**：阀门椭圆在阀下方；仪表圈两行（类别 / 回路号），上方；设备位号下划线。同一位号全套只出现一次。
- **注释要把功能讲清楚**：每张图的注释写明本图做什么、各路气体或水路的用途、关键设备和仪表的作用、联锁和图形符号的含义、专用缩写，让没参与设计的人能读懂；写满注释区也不要压图框和标题栏（注释顶边不高于最下一行位号 2 mm 以上，底边离图框 ≥ 5 mm）。
- **仪表精简原则**（设计会因此变复杂，故只画有用的）：
  - 画：规格书、技术方案点名要的；联锁、报警、停机判据用到的；操作人员需要现场读数的；安全相关的。
  - 不画：只有“工程假设”依据、又无联锁和操作用途的（如已有调压阀和流量控制的支路上的额外压力表、供水总管上的第二块压力变送器）；“需要时再加”的可选项（写进注释，不画）；同一设备的多个同类电参量（电压、电流、功率、电量合并成一个圈，圈外注明）。
  - 删仪表要同步改 `pid_model.json`、版面、联锁表和设计依据表。
- **禁区**：x>235 且 y<91 是标题栏和修订栏，任何内容不得进入。
- **措辞**：图面、属性、交付文件都不体现 AI 参与，也不写工具与过程、数据文件名、内部问题编号。角色栏未定写“—”，设计单位留空，类别写“设计确认”。

## 速查
| 要做的事 | 命令 |
|---|---|
| 新项目脚手架 | `python scripts\new_project.py <阶段目录> <项目名>` |
| 离线检查与预览 | `python scripts\plain_pipeline.py <_工作底稿> prep [图号…]` |
| 出图 / 重画 | `… draw [图号…] [--redraw] [--wait]`；`… status` 看进度 |
| 出图后收尾 | `… post`（PNG、清元数据、图集、扫描、zip 备份） |
| 设计依据表 | `python scripts\make_review.py <pid_model.json> <输出.xlsx>` |
| 联锁表与工况说明 | `python scripts\make_ce_modes.py <pid_model.json> <目录>`，再 `render_ce_modes.py` |
| 清单与对账 | `python scripts\export_lists.py <pid_model.json> <输出.xlsx> <成本表.xlsx\|-> <dcf\|->` |
| 单步工具 | `lint_specs.py`、`plain_convert.py`、`check_plain.py`、`preview_spec.py`、`render_pdfs.py`、`clean_pdf_meta.py`、`pack_pdfs.py` |
| 符号目录更新 | `catalog_from_info.py assets\symbol_catalog.json <*.info.log>` |

## 铁规则
- **AutoCAD 实例**：同一时间只开一个 AutoCAD；用户自己的 AutoCAD 在运行时**不启动引擎**（引擎检测到外来实例会直接停止，`draw` 也会先查）。要出图先请用户保存关闭。引擎只结束它自己启动的进程，不要用“杀所有 acad”之类的命令。
- **改动验证**：引擎、模板、符号库、`plain_convert.py` 的改动，先在验证项目跑一遍（`pipeline.json` 的 `project` 指向验证项目），通过后才用于正式项目。验证项目名不得带到正式图面。
- **版本**：产出出新版本，不覆盖旧版本；本地 `_恢复备份\` 留上一版项目 zip。
- **闪退**：停止本批，保留 `<Backup>\_故障留证\` 日志，用最近 zip 恢复，不直接改项目库文件。
- **脚本**：引擎脚本用 `powershell.exe`（Windows PowerShell 5），含中文的 `.ps1` 存 UTF-8 带 BOM；JSON 里的路径用正斜杠。
- **措辞**：见“图面标准”。

## 常见错误
| 现象 | 原因与处理 |
|---|---|
| 线看似没连上（差 1~4 mm） | 线端没落在符号连接点上。用 `attach()` 取实测点；lint 报 ERROR |
| 管嘴没接上管线 | 管嘴 `at` 要落在管线端点或管线上；lint 报“图面未连上”。管线穿壁时管嘴放壁上 |
| 线号压在设备或符号上 | 线段太短放不下。加长线、改标注点，或把设备移开留出长度（≥ 线号长度 + 4 mm） |
| 位号椭圆压到符号、仪表圈 | 间距不够；椭圆与相邻仪表圈至少留 2 mm，必要时调偏移 |
| 表格或注释压标题栏 | 修订栏顶边 89 mm；lint 检查 x>235、y<91 |
| “CO”印成“C□” | 文字样式必须是 gbenor+gbcbig，模板与符号库已统一 |
| 出图后 PDF 没有文字可抽取 | 正常，文字按曲线输出；位号核对用 `check_plain.py`（对照 spec），不要抽 PDF 文字 |
| `draw` 报已有 AutoCAD | 有线程的 acad 进程才算；僵尸进程（0 线程）不算。请用户保存关闭自己的 AutoCAD |

完整故障记录见 `references/pitfalls.md`；质检与记录模板见 `references/qa.md`；Plant 智能对象路线（已停用，仅备查）见 `references/engine.md` 末节。

## 已定的取舍
- **不再建 Plant 智能对象**：见概述。需要位号库、报表时，用 `export_lists.py` 由模型导出清单。
- **不并行多开 AutoCAD**：提速靠一个会话画完全部图纸，以及只重画改动的图。普通模式重画默认同一会话接着画。
- **不用 `accoreconsole` 做无头核查**：本机它不输出结果；核查靠 spec 检查和 PDF 逐张看。
- **暂不做 MCP 服务器**：瓶颈在会话启停和返工，不在调用方式。
