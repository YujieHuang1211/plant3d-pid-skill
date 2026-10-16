# 符号库

画图前先查符号库：不同设备用不同的图，不要随便拿一个框代替。库里共 211 个符号，按类别分：手动阀 24、流量与测量元件 23、减压与安全 20、仪表与逻辑 20、容器与储罐 19、管件与连接 18、泵与压缩机 17、设备 17、换热器 17、管嘴与法兰 15、调节阀与执行机构 12、过滤 9。

## 怎么查
```
python scripts\symbol_atlas.py find <关键词…> [--png 输出.png]
```
关键词中英文都行，多个词取交集，例如 `find 泵`、`find 换热器 --png hx.png`、`find 气瓶`、`find relief`。输出：样式名、中文名、类别、实际大小、符号来源、用途、所在图集页。`--png` 把命中的符号画成一张图，直接看形状。
整套图集（带中文名）在 `assets/symbol_atlas/符号库图集_01…08.png`，需要全面挑选时逐页看。

## 两类来源，两种用法
| 来源 | 数量 | 怎么画 | 说明 |
|---|---|---|---|
| **Plant 自带库**（PIP/ISA）及项目自定义 QMZ 样式 | 约 194 | 版面里写 `asset`（或设备用 `s.equip`），样式名取上表“样式名”；转换时变成块参照 `sym` | 阀门、仪表、泵、换热器、罐、安全阀等都有。**注意**：它们在 AutoCAD 里依赖项目符号库，`sym` 的 `scale` 是**绝对比例**（替代样式默认比例，默认比例见 `assets/plant_style_scales.json`），不写 `scale` 就是默认大小。有些设备样式默认尺寸很大（如 `Vessel Style` 高 300 mm），需要缩放时 `scale = 想要的倍数 × 默认比例` |
| **手工新增**（非智能对象，折线几何） | 18 | 同样写 `asset`，样式名取手工新增的名字；转换时直接画成折线，不依赖任何项目符号库 | 气瓶、电加热器、冷水机、冷阱、干燥器、科氏流量计、就地压力表、干式真空泵、注射泵、伴热带、分析仪、限流孔板、卧式容器、夹套反应釜、气袋、洗气瓶、快插接头、电源。`scale` 是倍数（1 = 默认大小） |

`plain_convert.py --geom-all`：Plant 库符号也按几何库画成折线（不依赖项目符号样式，便于脱离 Plant 环境出图）。默认只有手工新增的符号这样画。

## 版面里怎么用
- 在线件（阀、过滤器、流量计等，管线从中穿过）：用版面函数库里对应的函数（`s.hand`、`s.xv`、`s.pcv`、`s.special`…）。
- 设备（罐、泵、换热器、气瓶等）：`s.equip(位号, 样式名, [x, y], anno=…)`，管嘴用 `s.nozzle(…)`；设备位号要登记到 `pid_model.json` 的 `equipment`。
- 没有现成函数的符号：`s.items.append({'k': 'asset', 'id': '位号', 'style': '样式名', 'at': [x, y], 'rot': 0, 'props': {'Description': '…'}, 'auto': True})`。
- 连接点：手工新增符号的接口在 `assets/native_symbols.json` 的 `ports`（相对插入点），已写入符号目录，`attach()` 和 lint 可用。
- 出图前 `plain_pipeline.py prep` 的预览会按真实形状画出符号（几何库里有的）。

## 库里没有怎么办（可以上网搜）
1. 先 `find` 换几个关键词，中文、英文、同义词都试（例如“蒸馏塔”→ `VesselWithTrayedInternals`“板式塔”）。
2. 确实没有：上网搜标准图形——GB/T 6567.4 / 6567.5（管路系统图形符号）、HG/T 20505（过程测量与控制仪表的功能标志及图形符号）、ISO 10628、ISA 5.1、PIP PIC001；看形状、接口位置、常见简化画法。同类设备取国内化工制图习惯。
3. 在 `scripts/symbol_geom.py` 的 `DEFS` 里加一条：`'样式名': dict(zh='中文名', cat='类别', use='用途', ports={…接口…}, paths=[P(折线点列, closed, fill), …])`。几何用毫米，插入点放在符号中心，接口点按管线连接位置给；可用 `_rect`、`_arc`、`_circle`、`_zig` 辅助函数。
4. `python scripts\symbol_geom.py build-native`：生成 `assets/native_symbols.json`，同步符号目录和中文名表。
5. `python scripts\symbol_geom.py png <输出.png> <样式名>` 画出来目测，形状、大小、接口都对再用；
6. 用 `python scripts\symbol_geom.py sheet assets\symbol_atlas` 重生成整套图集 PNG，提交。

## 维护
- Plant 库符号的几何是从 AutoCAD 出的图集 PDF 里提取的（`extract_symbol_geom.py`），文件 `assets/symbols_geom.json`。Plant 库升级或需要重新测量时：
  1. `python scripts\symbol_atlas.py measure-spec <目录>` 生成测量 spec，`powershell.exe -File scripts\scan_symbols.ps1 …` 在 AutoCAD 里画出并导出 `info`；
  2. `symbol_atlas.py parse <info.log> assets\plant_symbols.json` 得到各样式外框；
  3. `symbol_atlas.py atlas-specs assets\plant_symbols.json <spec 目录>` 生成图集页，用 `build_set.ps1 -Plain` 出 PDF；
  4. `extract_symbol_geom.py <PDF 目录> <spec 目录> <输出目录>` 提取几何，`assets/symbols_geom.json` 取 `plant_symbols_geom.json` 去掉 `dot` 项后的内容。
- 样式默认比例来自 Plant 的 `stylesof` 输出（`assets/plant_style_scales.json`）。
- 已知：假定管嘴（`Assumed Nozzle Style`）本身没有几何，是 Plant 内部占位，P&ID 里的管嘴由 `plain_convert.py` 按法兰接管图形画出，不用它。
