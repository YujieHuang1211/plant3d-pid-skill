# plant3d-pid

为非标设备、测试台绘制、修改和核查 P&ID 图集的技能，Claude Code 与 Codex 通用。出图借助 AutoCAD Plant 3D 2026（简中）的绘图引擎，**图纸只用普通 CAD 图元**（符号块、多段线、文字、表格），不创建 Plant 智能对象：出图稳定、速度快，规范靠图层线宽、线断开、设备管嘴和流向箭头做到位。

入口是 `SKILL.md`：工作流（含用户确认关口）、图面标准、速查命令、铁规则。

## 一条龙
```
python scripts/new_project.py <阶段目录> <项目名>          # 建 _工作底稿（模型、版面模块、pipeline.json）
python scripts/plain_pipeline.py <_工作底稿> prep           # 离线检查与预览，数秒
python scripts/plain_pipeline.py <_工作底稿> draw --wait    # 一个 AutoCAD 会话出全套，约 6 分钟
python scripts/plain_pipeline.py <_工作底稿> post           # PNG、清元数据、图集、扫描、备份
```

## 内容
| 目录 | 说明 |
|---|---|
| `SKILL.md` | 工作流、图面标准、仪表精简原则、速查命令、铁规则、常见错误 |
| `references/` | 引擎与流水线（`engine.md`）、版面规则、`pid_model.json` 字段、故障记录、质检清单 |
| `scripts/` | 流水线 `plain_pipeline.py`；转换 `plain_convert.py`；检查 `lint_specs.py`、`check_plain.py`；预览 `preview_spec.py`；收尾 `render_pdfs.py`、`clean_pdf_meta.py`、`pack_pdfs.py`；版面函数库 `pidlib.py`；联锁表、工况说明、清单、设计依据表；脚手架。`verify_topology.py`、`check_orphans.py`、`reopen_check.py`、`repair_opc.py` 属已停用的 Plant 对象路线，仅备查 |
| `assets/` | 符号几何目录、项目配置模板、完整项目范例、引擎源码快照 |
| `agents/openai.yaml` | Codex 显示名与默认提示 |

## 安装
克隆到技能目录即可：

```
git clone https://github.com/YujieHuang1211/plant3d-pid-skill.git %USERPROFILE%\.claude\skills\plant3d-pid
git clone https://github.com/YujieHuang1211/plant3d-pid-skill.git %USERPROFILE%\.codex\skills\plant3d-pid
```

## 运行环境
- AutoCAD Plant 3D 2026 简体中文版（只作为绘图引擎）
- .NET 8 SDK（编译 PidBot 引擎）
- Python 3，需 pywin32、PyMuPDF、openpyxl、python-docx、Pillow
- 本机 Microsoft Word / Excel（Office 交付件的渲染核对）
- PidBot 引擎位于 `E:\05p_id图绘制中心\_PidBot`，源码快照见 `assets/engine_src_snapshot.zip`
- 引擎脚本用 Windows PowerShell 5（`powershell.exe`）运行，含中文的 `.ps1` 存 UTF-8 带 BOM
