# plant3d-pid

用 AutoCAD Plant 3D（2026 简中）为非标设备、测试台绘制、修改和核查 P&ID 图集的技能，Claude Code 与 Codex 通用。

入口是 `SKILL.md`。工作流、速查命令和铁规则都在里面。

## 内容
| 目录 | 说明 |
|---|---|
| `SKILL.md` | 工作流（含用户确认关口）、速查命令、铁规则、常见错误、已定取舍 |
| `references/` | 引擎命令、版面规则、`pid_model.json` 字段、故障记录、质检清单 |
| `scripts/` | 版面函数库 `pidlib.py`；出图前检查、离线预览、项目库核查、残留检查；联锁因果表、工况说明、清单、图集合并；新项目脚手架 |
| `assets/` | 符号几何目录、项目配置模板、完整项目范例、PidBot 引擎源码快照 |
| `agents/openai.yaml` | Codex 显示名与默认提示 |

## 安装
克隆到技能目录即可：

```
git clone https://github.com/YujieHuang1211/plant3d-pid-skill.git %USERPROFILE%\.claude\skills\plant3d-pid
git clone https://github.com/YujieHuang1211/plant3d-pid-skill.git %USERPROFILE%\.codex\skills\plant3d-pid
```

## 运行环境
- AutoCAD Plant 3D 2026 简体中文版
- .NET 8 SDK（编译 PidBot 引擎）
- Python 3，需 pywin32、PyMuPDF、openpyxl、python-docx、Pillow
- 本机 Microsoft Word / Excel（Office 交付件的渲染核对）
- PidBot 引擎位于 `E:\05p_id图绘制中心\_PidBot`，源码快照见 `assets/engine_src_snapshot.zip`
