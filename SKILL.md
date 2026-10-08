---
name: plant3d-pid
description: Use when drawing, revising or checking P&IDs (管道及仪表流程图) in AutoCAD Plant 3D for custom equipment or test-bench projects — a new P&ID set from a project folder (requirements, technical scheme, cost workbook), layout or connection fixes on existing sheets, interlock C&E or operating-mode tables, equipment/line/instrument lists — or when Plant 3D automation crashes (eNotOpenForWrite, eWasOpenForRead), hangs at startup, prints "?" tags, or shows lines that look unconnected.
---

# Plant 3D P&ID 出图

## 概述
数据流是：`pid_model.json`（工艺对象、连接、联锁、工况的唯一数据源）→ Python 版面模块生成绘图 spec → 出图前静态检查与离线预览 → 一个 AutoCAD 会话批量出图 → 项目库核查 → 交付。
**AutoCAD 只负责最终出图**。版面、连接几何、压框问题全部在离线检查和预览里解决，每改一次版面不必重画整套图。

引擎是 `E:\05p_id图绘制中心\_PidBot`（PidBot，C# 热加载插件 + PowerShell 驱动）。本技能的 `scripts/` 是通用 Python 工具，`assets/` 有符号几何目录、配置模板和一个完整项目示例。

## 何时用 / 不用
- 用：
  - 依据项目文件夹中的需求、技术方案、成本表，新出一套 P&ID；
  - 改已有图纸的版面、连接或属性；
  - 出联锁因果表、运行工况、设备/管线/仪表清单；
  - 排查 Plant 自动化故障。
- 不用：只画一张示意流程图（无 Plant 智能对象要求），这时直接用普通 CAD 或 drawio 更快。

## 工作流（每个 ★ 是用户确认关口）
1. 读项目文件夹：需求、技术方案、成本表的询价表与控制点位表、补充资料。新版本优先于旧版本。
2. 写 `pid_model.json`，字段见 `references/model_schema.md`。每个对象写明依据，分甲方输入、设计确认、工程假设三类。
3. ★ 用 `make_review.py` 生成《设计依据与连接关系表》xlsx，请用户确认拓扑和待定点。
4. 定分图（A3 多张）和编号规则，在 `sheets` 中列出图号与图名。
5. 写版面模块：`from pidlib import *`，参照 `assets/example/` 和 `references/layout_rules.md`。生成 spec 后：
   - `lint_specs.py`：0 ERROR 才能继续；
   - `preview_spec.py` 出 PNG，逐张看。
6. 新项目先运行 `setup_project.ps1`，再在后台运行 `build_set.ps1` 出图。与此同时并行生成 Office 交付件：`make_ce_modes.py`、`export_lists.py`。
7. 逐张看 PDF。有问题时：改版面 → lint/预览 → `build_set.ps1 -Redraw`，只重画改动的图。
8. 收尾：
   - `-Reopen` 重开核对；
   - 清单与上游对账；
   - `pack_pdfs.py` 合并图集；
   - 备份 zip。
9. ★ 列出对上游文件（技术方案、成本表等）的影响，只列不改，由用户决定。

命令与参数见 `references/engine.md`。

## 速查
| 要做的事 | 命令 |
|---|---|
| 新建 Plant 项目 | `powershell -File …\_PidBot\scripts\setup_project.ps1 -Name 项目名 -Parent E:\05p_id图绘制中心 -ProjProps <json>` |
| 生成 spec | `python 版面模块.py <specs目录>`（调用 `pidlib.build`） |
| 静态检查 | `python scripts\lint_specs.py <specs> 图号…` |
| 离线预览 | `python scripts\preview_spec.py <specs> <输出> 图号…` |
| 全套出图 | `powershell -File …\build_set.ps1 -Project … -Specs … -Pdf … -Backup … -Sheets "图号\|图名.dwg;…" [-Reopen]` |
| 只重画几张 | 同上加 `-Redraw`，`-Sheets` 只列要重画的图 |
| 库核查 / 残留 | `verify_topology.py`、`check_orphans.py`（`build_set` 已自动调用） |
| 新项目脚手架 | `python scripts\new_project.py <阶段目录> <项目名>`（打印后续全部命令） |
| 设计依据表 | `python scripts\make_review.py <pid_model.json> <输出.xlsx>` |
| 联锁表与工况说明 | `python scripts\make_ce_modes.py <pid_model.json> <目录>`，再 `render_ce_modes.py <目录> <QA目录>` |
| 清单与对账 | `python scripts\export_lists.py <pid_model.json> <输出.xlsx> <成本表.xlsx\|-> <ProcessPower.dcf>` |
| 合并图集 | `python scripts\pack_pdfs.py <pid_model.json> <PDF目录> <输出.pdf>` |
| 符号目录更新 | `catalog_from_info.py assets\symbol_catalog.json <*.info.log>` |

## 铁规则
- **措辞**：图面、属性、交付文件都不体现 AI 参与，也不写工具与过程，例如数据文件名、内部问题编号、套话免责声明。
  - 标题栏“设计”等角色栏未定时写“—”；设计单位未定时留空。
  - 类别写“设计确认”，不写“用户确认”。
- **改动验证**：引擎、模板、符号库的任何改动，先在验证项目 `_验证\…验证项目` 跑 TEST 图，验证通过后才用于正式项目。
- **闪退处理**：闪退或报 Plant 状态异常时，停止本批并保留日志，**不直接改项目库 dcf**。用 zip 恢复。
- **重画**：不在原项目上直接重画已有图纸。必须用 `-Redraw`（移除旧图 → 清空线组 → 重画 → 重配跨图连接器），或者恢复 zip。
- **AutoCAD 实例**：同一项目只开一个 AutoCAD。Plant 项目库是带文件锁的 SQLite，多开并行写入会损坏。可以并行的是 Office 交付件、清单和审查。

## 常见错误
| 现象 | 原因与处理 |
|---|---|
| 线看似没连上（差 1~4 mm） | 线端没落在符号连接点上。用 `attach()` 取实测点；lint 会报 ERROR |
| 位号带“?” | 闪退残留的位号登记，或删图后残留的空线组。用 `check_orphans.py` 查；恢复 zip 或 `-Redraw` |
| 连接器 A/B 与去向文字空白 | 连接器须开自动化放置，并且显式连接（两者都要） |
| 位号被吸到别的线或文字上 | 标注点前加 `_non`（引擎已处理） |
| “CO”印成“C□” | 标注文字样式是 txt.shx。模板与符号库已统一改为 gbenor+gbcbig |
| 表格或注释压标题栏 | 修订栏顶边 89 mm。lint 检查 x>235、y<91 |
| 启动后停在开始页、命令无效 | `Start-Acad` 已用 `/t` 带模板启动，失败会自动重启一次 |

完整故障记录见 `references/pitfalls.md`；质检与记录模板见 `references/qa.md`。

## 已定的取舍
- **不并行多开 AutoCAD**：原因见铁规则。提速靠两点：一个会话画完全部图纸（9 张约 8 min，其中启动约 2.5 min），以及只重画改动的图（约 6.5 min；不用再从该张起整串重画 30~45 min）。
- **暂不做 MCP 服务器**：瓶颈在会话启停和返工，不在调用方式；Claude Code 直接调 PowerShell/Python 已足够。若以后要从其他客户端驱动 Plant，再把 `pidbot.psm1` 包装成 MCP。
