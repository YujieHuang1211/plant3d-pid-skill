# 出图中断与恢复

先看状态，再决定怎么做。不要靠日志里有没有“全部完成”判断。

```
python scripts\plain_pipeline.py <_工作底稿> status      # 0 完成 / 1 失败或无记录 / 2 运行中或已中断
python scripts\plain_pipeline.py <_工作底稿> resume --dry-run   # 说明会怎么续，不启动 AutoCAD
python scripts\plain_pipeline.py <_工作底稿> resume --wait      # 续画
python scripts\plain_pipeline.py <_工作底稿> draw --changed --wait   # 改了模型/版面后，只画输入变化的图
python scripts\plain_pipeline.py <_工作底稿> reopen [图号…]         # 新会话重开 DWG 核对（不保存）
```

## 记录和清单在哪
| 文件 | 内容 |
|---|---|
| `_出图日志/run_<编号>.json` | 本次出图：状态（running/ok/failed/interrupted）、返回码、目标图张、各图输入哈希、问题列表 |
| `_出图日志/draw_<编号>.log` | 引擎日志（UTF-8），只用来看过程 |
| `_构建清单.json` | 每张图最近一次成功出图的输入哈希、DWG/PDF 哈希、运行编号；`--changed` 和 `resume` 据此判断 |
| `_恢复备份/*.zip` + `*.zip.manifest.json` | 引擎在每张图通过后打的检查点和它的身份清单（运行编号、已完成图张及 spec 哈希、zip 哈希） |

## 判断规则
- 一张图只有 DWG 和 PDF 都晚于本次出图开始、PDF 恰 1 页且图幅对，才算出完；旧文件存在不算。
- 输入变了（该图 spec 或图签属性、符号库、样式配置、引擎）的图一律重画，不沿用旧产物。图签有“共 N 张”，增减图张时每张都会变。
- `resume` 先把上次没走完的出图里已完整出完、输入没变的图认进清单，再只画其余的图。

## 引擎的自动恢复（build_set.ps1）
- 偶发故障（崩溃、卡死、对话框、超时）：留证到 `<Backup>\_故障留证\` → 校验检查点 → 用最近检查点恢复 → 新会话从该图重试。默认只重试 1 次（`pipeline.json` 的 `max_retry` 可调）；spec 或规则错误不重试，立即停止。
- 恢复前校验（`scripts/ckpt.py verify`）：zip 能完整打开、有身份清单、已完成图张的 spec 哈希与现在一致、zip 哈希未变。不符就拒绝恢复并保留现场，由人判断。没有清单的旧备份同样拒绝。
- 项目库（`*.dcf`，SQLite）打包时用在线备份接口取一致副本；2026-10-20 实测 AutoCAD 打开着项目时可读。
- 只结束本任务启动并登记了进程号的 AutoCAD，不动用户自己的实例。

## 处理顺序
1. `status`：2（已中断）或 1（失败）→ 看 `问题` 行和日志最后几行。
2. 失败原因是 spec/规则：先改，`prep` 通过后再 `draw --changed`。
3. 原因是 AutoCAD 偶发故障：`resume --wait`。连续两次仍失败，保留 `_故障留证` 交给用户，不无限重试，不直接改项目库文件。
4. 用户自己的 AutoCAD 在运行：请用户保存关闭；不要“杀所有 acad”。
