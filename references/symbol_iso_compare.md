# 符号与标准对照（ISO 10628-2:2012 / ISA-5.1-2024 / PIP）

回答"我们画的符号标不标准"。用量取 某示范项目的两张图（共 439 个符号）。判断依据：ISO 10628-2 表 2 原件页面（PDF 页 = 印刷页 + 4）。图形是自绘几何，条目号和登记号见 `assets/native_symbols.json` 各符号的 `basis`。

状态：**已换**＝pip-ref-a3 配置自动换成 ISO 符号；**可选**＝符号库里有 ISO 版，版面里要手动选用；**同**＝与标准一致；**非 ISO**＝ISO 10628-2 没有这个符号，属 ISA-5.1 / PIP / 项目简化。

| 符号（Plant 样式） | 用量 | ISO 10628-2 条目 | 状态 | 说明 |
|---|---|---|---|---|
| 球阀 Ball Valve（开/关） | 58 / 32 | 21.7（X8071） | 已换 | ISO 是菱形加圆；关位实心是项目约定 |
| 闸阀、截止阀、针阀、蝶阀 | 1–5 | 21.10 / 21.4 / 21.13 / 21.11 | 已换 | 原先 PIP 画法与 ISO 不同（闸阀竖线、截止阀圆点、针阀三角、蝶阀圆点加竖线） |
| 弹簧安全阀 QMZ Safety Valve | 14 | 23.1（X2124） | 已换 | 弹簧在上、阀座实心点加粗线。PIP 要求直立：版面用 `mirror` 保持 |
| 阻火器 Flame Arrestor | 3 | 23.4（2036） | 已换 | ISO 是格栅方框，不是带 F 的方框；防爆轰另有 23.6 |
| 管道过滤器 Filter Pipe | 8 | 24.6（X8090） | 已换 | 方框加斜虚线 |
| 止回阀 Check Valve | 15 | 22.1（X8077） | 保留 PIP | 已决定：PIP 画法自带明确流向标记；ISO 版（菱形加实心点）流向含义原件页面没有文字，未核对前不用 |
| 仪表圈、PLC 方框、联锁菱形 | 112 / 41 / 2 | —（ISA-5.1） | 同 | ISO 10628-2 不含仪表符号；形状、位置前缀按 ISA-5.1 |
| 立式容器 Vessel | 19 | 1.5（2062） | 可选 | Plant 容器尺寸和接口因项目而异，不自动换；`ISO Vertical Vessel Style` 供新版面使用 |
| 卧式容器 Horizontal Drum | 5 | 1.5 横置 | 可选 | `ISO Horizontal Vessel Style` |
| 外置列管冷凝器 | 4 | 3.3（2511） | 可选 | `ISO Heat Exchanger Fixed Tube Style`，接口位置与 Plant 样式不同 |
| 卧式离心泵 | 3 | 15.2（2322） | 可选 | `ISO Centrifugal Pump Style`；PIP 泵带电机，ISO 泵与电机分开画（电机 20.6） |
| 往复压缩机 | 2 | 16.3（X8097） | 可选 | `ISO Piston Compressor Style` |
| 电加热器、冷水机、科氏流量计、孔板（法兰）、夹套反应釜 | 3/2/9/2/1 | 无 | 非 ISO | 项目简化画法。夹套反应釜在 ISO 有 1.27（X8006）但组成复杂，暂保留 |
| 隔膜阀、自力式减压阀 | 1 / 1 | 无（ISO 14617-6 / PIP） | 非 ISO | 沿用 Plant 库符号 |
| 封堵帽、跨图连接器、界区接口 | 12 / 66 / 17 | 无 | 非 ISO | 管线端头与图纸接口，属 PIP 或项目约定（ISO 10628-1 规定接口做法） |

## 使用与维护
- 新项目默认 pip-ref-a3：线宽、断线、箭头参照 PIP，符号按 `symbol_map` 换成 ISO。旧项目 `profile` 缺省为 legacy，符号不变。
- 想对某个项目关掉替换：在 `pipeline.json` 的 `profile_overrides` 写 `{"symbol_map": {"*": null}}`（全关），或 `{"symbol_map": {"Ball Valve Style": null}}`（单个样式关）。
- 增加符号：`scripts/iso_symbols.py` 里加一条（带 `basis`），运行 `python scripts\symbol_geom.py build-native`；测试 `tests/test_iso_symbols.py` 会检查依据字段、闭合、端口与源符号一致。
- ISO 符号在 DWG 里是**一个符号一个块参照**（块名 `PIDBOT_<样式名>`），可整体移动、复制、改图层；块内线随块参照所在层的线宽。
