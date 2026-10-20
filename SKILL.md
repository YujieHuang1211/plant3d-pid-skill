---
name: plant3d-pid
description: Use when drawing, revising or checking P&IDs (管道及仪表流程图) as standard, editable DWG sheets with the AutoCAD Plant 3D engine (plain CAD entities, no smart objects) for custom equipment or test-bench projects — a new P&ID set from a project folder (requirements, technical scheme, cost workbook), layout or connection fixes on existing sheets, interlock C&E or operating-mode tables, equipment/line/instrument lists — or when the drawing engine crashes (eNotOpenForWrite), hangs at startup, or sheets show unconnected lines, overlapping text or missing nozzles.
---

# P&ID 出图（普通图元 DWG）

图纸只用普通 CAD 图元（符号块、多段线、文字、表格），不创建 Plant 智能对象（2026-10-16 用户定：智能对象路线在本机随机崩溃，验收看的是规范、可编辑的 DWG 和 PDF）。规范靠制图配置、图层线宽、断线、管嘴、箭头做到位。

数据流：`pid_model.json`（对象、连接、联锁、工况的唯一数据源）→ 版面模块 `sheets.py` 生成 spec → `plain_pipeline.py prep`（离线检查+转换+预览）→ `draw`（一个 AutoCAD 会话批量出图）→ `post`（核对产物、PNG、图集、扫描、备份）→ 人工逐张看 → 交付。AutoCAD 只负责最终出图，版面、连接、压框、重叠都在离线阶段解决。引擎在 `E:\05p_id图绘制中心\_PidBot`。

不用：只要一张示意流程图、不要图框和标准图层时，直接用 draw.io。

## 按需读什么（不要整套读）
| 要做的事 | 读 |
|---|---|
| 任何出图 | 本文件；项目 `pipeline.json` 的 `profile`（`assets/profiles/`） |
| 写/改模型 | `references/model_schema.md` |
| 写/改版面 | `references/layout_rules.md`、`scripts/patterns.py`（气源支路、控制回路）、`assets/example/` |
| 图面规则、标准依据 | `references/drawing-rules.md`、`references/standards-index.json`（按条款查原件，不整本读） |
| 找/加符号 | `references/symbol_library.md`、`python scripts\symbol_atlas.py find <关键词>` |
| 符号是否符合标准 | `references/symbol_iso_compare.md`（ISO 10628-2 对照）；ISO 符号定义在 `scripts/iso_symbols.py` |
| 出图中断、失败、闪退 | `references/recovery.md`；`references/pitfalls.md`、`references/engine.md`（故障时才读） |
| 质检与交付 | `references/qa.md` |

## 工作流（★ 为用户确认关口）
1. 读项目文件夹：需求、技术方案、成本表的询价表与控制点位表、补充资料；新版本优先。
2. 写 `pid_model.json`，每个对象写明依据（甲方输入 C / 设计确认 U / 工程假设 E）。仪表取舍见 `drawing-rules.md`；设备和元件先 `symbol_atlas.py find` 查符号库，不同设备用不同的图。
3. ★ `make_review.py` 生成《设计依据与连接关系表》，请用户确认拓扑和待定点。
4. 定分图和编号写进 `sheets`；一图一个清楚的工艺任务，挤了先拆图。
5. `python scripts\new_project.py <阶段目录> <项目名>` 建 `_工作底稿/`（写入 `profile: pip-ref-a3`）。
6. 写版面模块（`from pidlib import *`；重复的支路、回路用 `patterns.py`，只写有哪些元件和接到哪里）。
7. `python scripts\plain_pipeline.py <_工作底稿> prep`：版面 → lint → 转换 → 普通版 lint → check_plain → check_numbering → validate_views（模型对象与连接都画进图了没有）→ 预览。全部 OK 才能出图；逐张看 `预览/`。输出只列失败项，完整输出才在失败时展开。
8. `plain_pipeline.py <…> draw --wait`；改了之后只画输入有变化的图：`draw --changed --wait`（都没变不启动 AutoCAD）；指定重画：`draw P&ID-103 --redraw`；中断后：`resume --wait`。
9. `plain_pipeline.py <…> reopen`（已变更的图，新会话重开 DWG 核对数量、文字、图层、越框，约 4 分钟）；`plain_pipeline.py <…> post`，逐张看 `终审PNG/`（截断、压框、重叠、线是否落在符号上、管嘴、标题栏字段）。有问题回第 6 步。
10. ★ 版次递增（R0→R1）：不覆盖旧版，交付目录另放 `R1\`；`meta.rev`、`meta.rev_note` 同步。项目在云盘时先本地生成自查，完成后一次复制进去。
11. ★ 列出对上游文件（技术方案、成本表等）的影响，只列不改。

并行可做：`make_ce_modes.py`（联锁表、工况说明）、`export_lists.py`（清单）。

## 需要用户决定的事
改变工艺功能、安全功能、合同要求；制图配置与客户要求冲突；图幅要不要换；资料不足的仪表留不留。其余例行修改（版面、间距、编号整理）直接做。

## 退出码与结果
- `prep`、`draw`、`post` 返回 0 才算成功；`status` 返回 0 完成 / 1 失败或无记录 / 2 运行中或已中断。成败只看 `_出图日志/run_*.json`，不看日志里有没有“全部完成”字样。
- `post` 先核对产物：DWG 齐全、单张 PDF 恰 1 页且图幅对、都不早于本次出图；不通过就中止，不合并图集。
- lint 警告带编号 `[W-…]`；文字重叠类默认必须处置，确属正常的在 `_工作底稿/accepted_warnings.json` 登记（编号、位置、理由；图 spec 变了即失效）。
- 老项目补录模型期间可在 `pipeline.json` 写 `"views": "warn"`，模型核对只列不挡。

## 速查
| 要做的事 | 命令 |
|---|---|
| 新项目脚手架 | `python scripts\new_project.py <阶段目录> <项目名>` |
| 离线检查与预览 | `python scripts\plain_pipeline.py <_工作底稿> prep [图号…]` |
| 出图 / 增量 / 续画 / 进度 | `… draw [图号…] [--redraw] [--changed] [--wait]`；`… resume [--dry-run]`；`… status` |
| 重开核查 / 出图后收尾 | `… reopen [图号…]`；`… post` |
| 设计依据表 | `python scripts\make_review.py <pid_model.json> <输出.xlsx>` |
| 联锁表与工况说明 | `python scripts\make_ce_modes.py <pid_model.json> <目录>`，再 `render_ce_modes.py` |
| 清单与对账 | `python scripts\export_lists.py <pid_model.json> <输出.xlsx> <成本表.xlsx\|-> <dcf\|->` |
| 单步工具 | `lint_specs.py`、`plain_convert.py`、`check_plain.py`、`check_numbering.py`、`validate_views.py`、`preview_spec.py`、`render_pdfs.py`、`clean_pdf_meta.py`、`pack_pdfs.py` |
| 回归测试 | `cd tests && python -m unittest discover -s .` |

## 铁规则
- 出图期间（约 6 分钟）不要点 AutoCAD；点过就对受影响的图 `draw <图号> --redraw`。同一时间只开一个 AutoCAD，用户自己的 AutoCAD 在运行时不启动引擎（引擎只结束自己启动的进程，不要“杀所有 acad”）。
- 改引擎、模板、符号库、`plain_convert.py`、制图配置，先在验证项目跑通再用于正式项目；验证项目名不得带到正式图面。
- 产出出新版本，不覆盖旧版本；本地 `_恢复备份\` 留上一版项目 zip。
- 闪退：引擎自动校验检查点并重试 1 次；仍失败就保留 `<Backup>\_故障留证\` 交给用户，不无限重试，不直接改项目库文件（见 `references/recovery.md`）。
- 引擎脚本用 `powershell.exe`（Windows PowerShell 5）；含中文的 `.ps1` 存 UTF-8 带 BOM；JSON 路径用正斜杠。本机已装 PowerShell 7，脚本语法解析通过，但未在 CAD 上实测，不迁移（出图时间主要在 AutoCAD，换壳层没有收益）。
- 措辞：图面、属性、交付文件不体现 AI 参与，不写工具与过程、数据文件名、内部问题编号。

## 已定的取舍
- 不再建 Plant 智能对象；需要位号库、报表时用 `export_lists.py` 由模型导出。
- 不并行多开 AutoCAD：提速靠一个会话画完全部图纸，以及只重画改动的图。
- 不用 `accoreconsole` 做无头核查（本机不输出结果）。
- 暂不做 MCP 服务器：瓶颈在会话启停和返工，不在调用方式。
