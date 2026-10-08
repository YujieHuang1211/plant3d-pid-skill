"""单张重画后重新配对跨图连接器：从其他图的 spec 中挑出引用了被重画图对象的 opc 配对项，写成一个只含 opc 项的小 spec。
Drawer 的 opc 用 DataLinksManager.Relate 建立 ConnectorsRelationship，对方图纸不必打开；在任一打开的图纸中执行 draw 即可。
用法: python repair_opc.py <specs目录> <被重画图号,逗号分隔> <输出 spec.json>
小 spec 须放在 specs 目录内（id 由同目录全部 *.ids.json 解析）。打印配对数；0 时不写文件。
"""
import json
import sys
from pathlib import Path


def spec_items(f):
    return json.loads(Path(f).read_text(encoding='utf-8'))['items']


def main(specdir, sheets, out):
    specdir = Path(specdir)
    redrawn = [s.strip() for s in sheets.split(',') if s.strip()]
    ids = set()
    for s in redrawn:
        ids |= {it['id'] for it in spec_items(specdir / f'{s}.json') if it.get('id')}
    pairs = []
    for f in sorted(specdir.glob('*.json')):
        if f.name.endswith(('.props.json', '.ids.json')) or f.stem in redrawn or f.stem.startswith('_'):
            continue
        try:
            items = spec_items(f)
        except (KeyError, json.JSONDecodeError):
            continue
        for it in items:
            if it.get('k') == 'opc' and (it['a'] in ids or it['b'] in ids):
                pairs.append({'k': 'opc', 'a': it['a'], 'b': it['b']})
    print('opc 重新配对', len(pairs), '项')
    if pairs:
        Path(out).write_text(json.dumps({'clear': False, 'items': pairs}, ensure_ascii=False, indent=1), encoding='utf-8')
    return len(pairs)


if __name__ == '__main__':
    main(*sys.argv[1:4])
