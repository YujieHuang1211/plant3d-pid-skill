"""普通图元模式的内容核查（替代 verify_topology / check_orphans）：对照 Plant 版 spec（数据源）检查普通版 spec 的文字。
用法: python check_plain.py <Plant 版 specs 目录> <普通版 specs 目录> [--ban 词1,词2,…]
检查：
  1. 每个设备/阀门/仪表位号都有对应文字；仪表圈内两行（类别 / 回路号）都在
  2. 每条带线号的管线，线号文字存在
  3. 位号全套唯一（同一位号不得画在两处，跨图连接器和图例除外）
  4. 全部文字不含乱码（U+FFFD）、连续问号、禁用词（AI 参与痕迹、工具名、数据文件名、内部编号等）
退出码：全部通过 0，否则 1。
"""
import json
import re
import sys
from pathlib import Path

SKIP_STYLES = {'Off Page Connector Style', 'QMZ Battery Limit Style', 'Cap Style', 'Flow Arrow Style'}
BAN = ['AI', 'Claude', 'Codex', 'GPT', 'PidBot', 'Plant', 'AutoCAD', 'json', '.py', 'ids', '验证', 'P47', 'TODO', 'TEST', '用户确认', 'PQ-', '占位']


def strip_code(s):
    """去掉 MText 控制码：下划线、换行、带分号的字体码和堆叠码，以及大括号"""
    s = re.sub(r'\\[LlPp]', '', s)
    s = re.sub(r'\\[A-Za-z][^;\\]*;', lambda m: m.group(0)[2:-1].replace('^', '') if m.group(0).startswith('\\S') else '', s)
    return re.sub(r'[{}]', '', s)


def main(argv):
    ban = list(BAN)
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == '--ban':
            ban += [w for w in argv[i + 1].split(',') if w]; i += 2; continue
        args.append(argv[i]); i += 1
    src, dst = Path(args[0]), Path(args[1])
    errs, warns = [], []
    seen = {}
    for f in sorted(src.glob('P&ID-*.json')):
        if f.name.endswith(('.props.json', '.ids.json')):
            continue
        no = f.stem
        orig = json.loads(f.read_text(encoding='utf-8'))['items']
        pf = dst / f.name
        if not pf.exists():
            errs.append(f'{no}: 缺普通版 spec'); continue
        plain = json.loads(pf.read_text(encoding='utf-8'))['items']
        texts = [strip_code(it['text']) for it in plain if it['k'] == 'text']
        blob = '\n'.join(texts)
        tokens = set()
        for t in texts:
            tokens.update(re.split(r'\s+|\n', t))
        for it in orig:
            if it['k'] in ('asset', 'cv'):
                st = it.get('style') or it.get('body')
                if st in SKIP_STYLES or it['id'].startswith(('BL-', 'OPC-')):
                    continue
                tag = it['id']
                a, _, b = tag.partition('-')
                ok = tag in blob or (b and a in tokens and b in tokens)
                if not ok:
                    errs.append(f'{no}: 位号 {tag} 在普通版里没有文字')
                seen.setdefault(tag, []).append(no)
            elif it['k'] == 'line' and it.get('group') and it.get('anno'):
                g = it['group']
                ln = '-'.join(str(g.get(k, '')) for k in ('Service', 'LineNumber', 'NominalSize', 'NominalSpec'))
                if ln not in blob:
                    errs.append(f'{no}: 线号 {ln} 在普通版里没有文字')
        for t in texts:
            if '�' in t or '??' in t:
                errs.append(f'{no}: 文字含乱码或连续问号：{t[:30]}')
            for w in ban:
                hit = re.search(r'(?<![A-Za-z])' + re.escape(w) + r'(?![A-Za-z])', t) if w.isascii() and w.isalpha() and len(w) <= 3 else (w.lower() in t.lower())
                if hit:
                    errs.append(f'{no}: 文字含禁用词“{w}”：{t[:40]}')
    for tag, sheets in sorted(seen.items()):
        if len(sheets) > 1:
            errs.append(f'位号 {tag} 出现在多张图：{"、".join(sheets)}')
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('WARN ', w)
    print('CHECK_PLAIN', 'PASS' if not errs else f'FAIL {len(errs)}', '位号数', len(seen))
    return not errs


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
