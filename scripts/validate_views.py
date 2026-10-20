"""模型 ↔ 图面核对（离线，不需要 AutoCAD）：证明 pid_model.json 里的对象和连接真的画进了图。
用法: python validate_views.py <pid_model.json> <Plant 版 specs 目录> <普通版 specs 目录> [--json 结果.json] [--warn-only]
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
OPC_STYLE = 'Off Page Connector Style'
KINDS = (('boundary', 'id'), ('equipment', 'tag'), ('inline', 'tag'), ('instruments', 'tag'), ('interlocks', 'id'))


def dist_seg(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L))
    return ((p[0] - ax - t * vx) ** 2 + (p[1] - ay - t * vy) ** 2) ** 0.5


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
    refs = []            # 引用表示（ref_of 指向主表示的位号）
    opc_reps = {}
    connects = []        # (图号, 线号, 对象 id, ctx)
    spec_line_nos = set()
    for no, items in plant.items():
        ln_of, pts_of = {}, {}
        for it in items:
            if it['k'] == 'line':
                ln = line_no(it)
                ln_of[it['id']] = ln
                pts_of[it['id']] = it['pts']
                if ln:
                    spec_line_nos.add(ln)
            elif it['k'] in ('asset', 'cv'):
                if it.get('style') == OPC_STYLE:        # 跨图连接器按样式认，不靠 id 前缀（项目里常叫 O-xxx-IN）
                    opc_reps.setdefault(it['id'], []).append((no, it))
                elif it.get('ref_of'):
                    refs.append((no, it))
                else:
                    reps.setdefault(it['id'], []).append((no, it))
        for it in items:
            if it['k'] == 'connect' and ln_of.get(it['line']):
                connects.append((no, ln_of[it['line']], it['asset'], it.get('ctx')))
            elif it['k'] == 'nozzle' and it.get('on'):      # 设备经管嘴接线：管嘴落在线上（含线端）就算设备接在这个线号上
                for lid, pts in pts_of.items():
                    if ln_of.get(lid) and any(dist_seg(it['at'], pts[i], pts[i + 1]) <= 1.0 for i in range(len(pts) - 1)):
                        connects.append((no, ln_of[lid], it['on'], 'nozzle'))
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
        if tag not in objs:
            errs.append(f'{tag}: 图面（{got[0][0]}）上有，模型里没有，属未批准新增')
    for no, it in refs:
        if it['ref_of'] not in reps and not (objs.get(it['ref_of']) or {}).get('omitted'):
            errs.append(f'{no} {it["id"]}: 引用的 {it["ref_of"]} 没有主表示')
    # 2. 位号绑定
    for tag, got in reps.items():
        if tag not in objs or tag.startswith('BL-'):
            continue
        for no, it in got:
            if (it.get('style') or it.get('body')) in SKIP_STYLES or it.get('ref_of'):
                continue
            texts = [{'at': t['at'], 'text': strip_code(t['text']).replace('\n', '')} for t in plain.get(no, []) if t['k'] == 'text']
            if not bound(texts, tag, label_point(it)):
                errs.append(f'{no} {tag}: 位号文字不在对象标注点 {BIND_R:g} mm 内（全图有相同字样也不算）')
    # 3. 线与对象
    on_line = {}
    any_line = {aid for _, _, aid, _ in connects}
    for no, ln, aid, ctx in connects:
        on_line.setdefault(ln, set()).add(aid)
    for l in model.get('lines', []):
        ln = l['no']
        if l.get('omitted'):
            continue
        if ln not in spec_line_nos:
            errs.append(f'{ln}: 模型里有这条线，图上没有这个线号')
            continue
        seq = l.get('seq', [])
        for i, tok in enumerate(seq):
            base = tok.split(':')[0]
            if ':' in tok or base not in objs or objs[base].get('omitted') or base not in reps:
                continue
            if base in on_line.get(ln, set()):
                continue
            if i in (0, len(seq) - 1) and base in any_line:      # 序列首尾常是相邻线号交界处的元件，接在相邻线上也算
                continue
            errs.append(f'{base}: 模型说在线 {ln} 上，图上没有接在这个线号的线上')
    # 4. 跨图连接器
    where = {tag: got[0][0] for tag, got in opc_reps.items()}
    item_of = {tag: got[0][1] for tag, got in opc_reps.items()}
    ln_of_opc = {}
    for no, ln, aid, ctx in connects:
        if aid in opc_reps:
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
                warns.append(f'{a}↔{b}: 两端线号不一致 {la} / {lb}（同一根管线跨图应保持同一线号；若项目按图张分段编号，请在图注说明）')
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
    if '--warn-only' in argv:         # 老项目补录期间：问题照列，但不挡出图（pipeline.json 里 "views": "warn"）
        warns, errs = errs + warns, []
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
