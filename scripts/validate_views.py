"""模型 ↔ 图面核对（离线，不需要 AutoCAD）：证明 pid_model.json 里的对象和连接真的画进了图。
用法: python validate_views.py <pid_model.json> <Plant 版 specs 目录> <普通版 specs 目录> [--json 结果.json]
检查：
  1. 覆盖：模型里每个设备/在线件/仪表/界区/联锁都有主表示（spec 里 id 相同的 asset/cv），或在模型里写了 omitted: "原因"；
     模型写了 sheet 的，必须画在那张图上（没写则只要求整套图里有）；spec 里出现模型没有的对象（跨图连接器 OPC- 除外）= 未批准新增
  2. 位号绑定：位号文字（仪表圈的两行，或整串位号）必须落在对象标注点 BIND_R 以内，不能靠全图搜到相同字样就算数
  3. 线与对象：模型 lines[].seq 里的对象必须在图上接在该线号的线上（connect）；线号本身要画出来
  4. 跨图：OPC 两端都在、图号互指、所接线号一致
退出码：无 ERROR 为 0。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_plain import SKIP_STYLES, strip_code  # noqa: E402

BIND_R = 8.0            # 位号文字中心到对象标注点的最大距离（mm）；仪表圈两行文字各偏 ±1.5，椭圆/下划线位号贴着标注点
KINDS = (('boundary', 'id'), ('equipment', 'tag'), ('inline', 'tag'), ('instruments', 'tag'), ('interlocks', 'id'))


def line_no(it):
    g = it.get('group') or {}
    return '-'.join(str(g.get(k, '')) for k in ('Service', 'LineNumber', 'NominalSize', 'NominalSpec')) if g else None


def model_objects(model):
    objs = {}
    for kind, key in KINDS:
        for x in model.get(kind, []):
            if x.get(key):
                objs[x[key]] = x
    return objs


def label_point(it):
    return (it.get('anno') or {}).get('at') or it['at']


def near(texts, pt, s):
    return any(t['text'] == s and abs(t['at'][0] - pt[0]) <= BIND_R and abs(t['at'][1] - pt[1]) <= BIND_R for t in texts)


def bound(texts, tag, pt):
    """整串位号，或按 plain_convert 的拆法（第一个 - 前后两行）都落在标注点旁"""
    if near(texts, pt, tag):
        return True
    a, _, b = tag.partition('-')
    return bool(b) and near(texts, pt, a) and near(texts, pt, b)


def validate(model, plant, plain):
    """plant / plain：{图号: items}。返回 (errs, warns)"""
    errs, warns = [], []
    objs = model_objects(model)
    reps = {}            # 位号 → [(图号, item)]
    lines = {}           # 线 id → 线号（按图）
    opcs = {}
    connects = []        # (图号, 线号, 对象 id, ctx)
    spec_line_nos = set()
    for no, items in plant.items():
        ln_of = {}
        for it in items:
            if it['k'] == 'line':
                ln = line_no(it)
                ln_of[it['id']] = ln
                if ln:
                    spec_line_nos.add(ln)
            elif it['k'] in ('asset', 'cv'):
                reps.setdefault(it['id'], []).append((no, it))
        for it in items:
            if it['k'] == 'connect' and ln_of.get(it['line']):
                connects.append((no, ln_of[it['line']], it['asset'], it.get('ctx')))
    # 1. 覆盖
    for tag, x in objs.items():
        if x.get('omitted'):
            continue
        got = reps.get(tag, [])
        if not got:
            errs.append(f'{tag}: 模型里有，整套图都没有主表示（要画，或在模型里写 omitted: "原因"）')
            continue
        want = x.get('sheet')
        if want and want not in {s for s, _ in got}:
            errs.append(f'{tag}: 模型指定在 {want}，实际画在 {"、".join(sorted({s for s, _ in got}))}')
    for tag, got in reps.items():
        if tag not in objs and not tag.startswith('OPC-'):
            errs.append(f'{tag}: 图面（{got[0][0]}）上有，模型里没有，属未批准新增')
    # 2. 位号绑定
    for tag, got in reps.items():
        if tag not in objs or tag.startswith(('BL-', 'OPC-')):
            continue
        for no, it in got:
            if (it.get('style') or it.get('body')) in SKIP_STYLES or it.get('ref_of'):
                continue
            texts = [{'at': t['at'], 'text': strip_code(t['text']).replace('\n', '')} for t in plain.get(no, []) if t['k'] == 'text']
            if not bound(texts, tag, label_point(it)):
                errs.append(f'{no} {tag}: 位号文字不在对象标注点 {BIND_R:g} mm 内（全图有相同字样也不算）')
    # 3. 线与对象
    on_line = {}
    for no, ln, aid, ctx in connects:
        on_line.setdefault(ln, set()).add(aid)
    for l in model.get('lines', []):
        ln = l['no']
        if ln not in spec_line_nos:
            errs.append(f'{ln}: 模型里有这条线，图上没有这个线号')
            continue
        for tok in l.get('seq', []):
            base = tok.split(':')[0]
            if ':' in tok or base not in objs or objs[base].get('omitted'):
                continue
            if base in reps and base not in on_line.get(ln, set()):
                errs.append(f'{base}: 模型说在线 {ln} 上，图上没有接在这个线号的线上')
    # 4. 跨图连接器
    where = {tag: no for tag, got in reps.items() for no, _ in got[:1] if tag.startswith('OPC-')}
    item_of = {tag: got[0][1] for tag, got in reps.items() if tag.startswith('OPC-')}
    ln_of_opc = {}
    for no, ln, aid, ctx in connects:
        if aid.startswith('OPC-'):
            ln_of_opc[aid] = ln
    for no, items in plant.items():
        for it in items:
            if it['k'] != 'opc':
                continue
            a, b = it['a'], it['b']
            if a not in item_of or b not in item_of:
                errs.append(f'{no}: 跨图连接器 {a}↔{b} 有一端没有画出')
                continue
            sa, sb = where[a], where[b]
            if sa == sb:
                errs.append(f'{a}↔{b}: 两端在同一张图 {sa}')
            for me, other, so in ((a, b, sb), (b, a, sa)):
                dest = (item_of[me].get('props') or {}).get('OriginOrDestination', '')
                if not dest.startswith(so):
                    errs.append(f'{me}: 去向文字“{dest[:20]}”没有指向对端图号 {so}')
            la, lb = ln_of_opc.get(a), ln_of_opc.get(b)
            if la and lb and la != lb:
                errs.append(f'{a}↔{b}: 两端线号不一致 {la} / {lb}')
    return errs, warns


def load_dir(d):
    out = {}
    for f in sorted(Path(d).glob('P&ID-*.json')):
        if f.name.endswith(('.props.json', '.ids.json')):
            continue
        out[f.stem] = json.loads(f.read_text(encoding='utf-8')).get('items', [])
    return out


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    js = argv[argv.index('--json') + 1] if '--json' in argv else None
    if js:
        args.remove(js)
    model = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    errs, warns = validate(model, load_dir(args[1]), load_dir(args[2]))
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('WARN ', w)
    print('VIEWS', 'PASS' if not errs else f'FAIL {len(errs)}', 'warn', len(warns))
    if js:
        Path(js).write_text(json.dumps({'errors': errs, 'warnings': warns}, ensure_ascii=False, indent=1), encoding='utf-8')
    return not errs


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
