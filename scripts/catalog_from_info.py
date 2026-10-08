"""由 PidBot `info` 导出（重开核对时生成的 *.info.log）建立符号库几何目录 symbol_catalog.json。
每个样式记录：相对插入点的外框 [dx0,dy0,dx1,dy1]、连接点偏移 [[dx,dy],…]、比例；按 0° 记录（其他角度由 lint/preview 旋转换算）。
用法: python catalog_from_info.py <输出 symbol_catalog.json> <info.log> [info.log …]
同一样式多次出现时取 0° 的第一个；已存在的目录会合并（新数据覆盖同名样式）。
"""
import json
import math
import re
import sys
from pathlib import Path

LINE = re.compile(r'\[(-?[\d.]+),(-?[\d.]+)\]-\[(-?[\d.]+),(-?[\d.]+)\] style=(.+?) pos=\((-?[\d.]+),(-?[\d.]+)\) ang=(-?\d+) scale=([\d.]+)(?: att=(\S*))?')
PT = re.compile(r'\((-?[\d.]+),(-?[\d.]+)\)')


def rot(dx, dy, ang):
    a = math.radians(ang)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def main(out, *logs):
    out = Path(out)
    cat = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    n = 0
    for lg in logs:
        for line in Path(lg).read_text(encoding='utf-8', errors='replace').splitlines():
            m = LINE.search(line)
            if not m:
                continue
            x0, y0, x1, y1 = map(float, m.group(1, 2, 3, 4))
            style, px, py, ang, sc = m.group(5), float(m.group(6)), float(m.group(7)), int(m.group(8)) % 360, float(m.group(9))
            atts = [(float(a) - px, float(b) - py) for a, b in PT.findall(m.group(10) or '')]
            # 统一换算为 0°：把实测偏移反向旋转
            back = [rot(dx, dy, -ang) for dx, dy in atts]
            corners = [rot(dx, dy, -ang) for dx, dy in ((x0 - px, y0 - py), (x1 - px, y1 - py), (x0 - px, y1 - py), (x1 - px, y0 - py))]
            if style in cat and cat[style].get('from_ang', 0) == 0 and ang != 0:
                continue
            cat[style] = {
                'bbox': [round(min(c[0] for c in corners), 2), round(min(c[1] for c in corners), 2),
                         round(max(c[0] for c in corners), 2), round(max(c[1] for c in corners), 2)],
                'att': [[round(a, 2), round(b, 2)] for a, b in back],
                'scale': sc, 'from_ang': ang,
            }
            n += 1
    out.write_text(json.dumps(dict(sorted(cat.items())), ensure_ascii=False, indent=1), encoding='utf-8')
    print('样式', len(cat), '（本次读取', n, '个对象）→', out)


if __name__ == '__main__':
    main(*sys.argv[1:])
