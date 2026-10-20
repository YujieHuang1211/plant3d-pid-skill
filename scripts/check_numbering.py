"""编号与交叉引用核查（出图前，离线）：
用法: python check_numbering.py <pid_model.json> <普通版 specs 目录> [--profile 配置名]
检查：
  1. 线号 物料-主项序号-外径-等级：序号不得重复；配置 numbering.mode=continuous（legacy）时每个主项内从 01 起连续，
     stable（新项目）时允许缺号（修订删线不强制重编），缺号提示，可在模型 retired.line_seq 登记作废号
  2. 联锁编号 I-xx 从 I-01 起连续；图上文字里出现的 I-xx 都在模型里
  3. 图上文字里出现的位号（如 XV-261、PCV-104、E-101）都在模型里（设备、在线件、仪表、界区）——
     删了元件却漏改注释、联锁表、图例时在这里报出
  4. 回路：按模型 loops[] 核对测量、控制功能、最终元件都存在；continuous 且没有 loops 时才用旧的 FIC→PCV/PI/XV 同号提示
     位号格式可由 conventions.tag_pattern 配置（缺省 字母-三位数字；V101 这类无连字符位号需配置）
退出码：无 ERROR 为 0。
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def strip(s):
    s = re.sub(r'\\[LlPp]', '', s)
    s = re.sub(r'\\S([^;]*);', lambda m: m.group(1).replace('^', ''), s)
    return re.sub(r'\\[A-Za-z][^;]*;', '', s)


def main(model, specs, profile=None):
    import drawprofile
    mode = drawprofile.load(profile).get('numbering', {}).get('mode', 'continuous')
    stable = mode == 'stable'
    M = json.loads(Path(model).read_text(encoding='utf-8'))
    retired = M.get('retired') or {}
    errs, warns = [], []
    # 1. 线号：序号不得重复；continuous 模式要求每个主项内连续，stable 模式缺号只提示（登记在 retired.line_seq 的不提示）
    groups = defaultdict(list)
    seen = {}
    for l in M['lines']:
        p = l['no'].split('-')
        seq = p[1]
        if seq in seen:
            errs.append(f'线号序号重复：{seen[seq]} 与 {l["no"]}')
        seen[seq] = l['no']
        groups[seq[:2]].append(int(seq[2:]))
    gone = set(retired.get('line_seq', []))
    for g, v in sorted(groups.items()):
        exp = list(range(1, max(v) + 1)) if stable else list(range(1, len(v) + 1))
        if sorted(v) != exp:
            miss = sorted(set(exp) - set(v))
            if stable:
                miss = [m for m in miss if f'{g}{m:02d}' not in gone]
                if miss:
                    warns.append(f'主项 {g} 的线号序号有缺号 {miss}（修订删线后可保留缺号；请在模型 retired.line_seq 登记作废号）')
            else:
                errs.append(f'主项 {g} 的线号序号不连续：已有 {sorted(v)}，缺 {miss}')
    # 2. 联锁
    ids = [i['id'] for i in M.get('interlocks', [])]
    if len(set(ids)) != len(ids):
        errs.append(f'联锁编号重复：{sorted(ids)}')
    elif stable:
        nums = sorted(int(i[2:]) for i in ids)
        gone_il = set(retired.get('interlocks', []))
        miss = [k for k in range(1, (nums[-1] if nums else 0) + 1) if k not in nums and f'I-{k:02d}' not in gone_il]
        if miss:
            warns.append('联锁编号有缺号 ' + '、'.join(f'I-{k:02d}' for k in miss) + '（可在模型 retired.interlocks 登记作废号）')
    else:
        want = [f'I-{k:02d}' for k in range(1, len(ids) + 1)]
        if sorted(ids) != want:
            errs.append(f'联锁编号不连续：{sorted(ids)}')
    # 3. 位号引用（位号格式可在 conventions.tag_pattern 里配置，缺省为“字母-三位数字”）
    tags = set()
    for k in ('equipment', 'inline', 'instruments', 'boundary'):
        for x in M.get(k, []):
            tags.add(x.get('tag') or x.get('id'))
    tp = (M.get('conventions') or {}).get('tag_pattern') or r'[A-Z]{1,4}-\d{3}[A-Z]?'
    pat = re.compile(r'(?<![A-Za-z0-9&])(' + tp + r')(?![A-Za-z0-9])')
    gone_tags = set(retired.get('tags', []))
    for f in sorted(Path(specs).glob('P&ID-*.json')):
        if f.name.endswith(('.props.json', '.ids.json')):
            continue
        for it in json.loads(f.read_text(encoding='utf-8'))['items']:
            if it['k'] != 'text':
                continue
            t = strip(it['text']).replace(chr(10), '')
            for m in pat.finditer(t):
                tag = m.group(1)
                if tag.startswith('P&') or re.match(r'(CO2|H2|PG|SG|TG|VT|DR|MG|CWS|CWR|FG)-', tag):
                    continue
                if tag.startswith('I-'):
                    continue
                if tag not in tags and tag not in gone_tags:
                    errs.append(f'{f.stem} 文字里的位号 {tag} 不在模型里：{t[:30].strip()}…')
            for m in re.finditer(r'(?<![A-Za-z0-9])(I-\d\d)(?![A-Za-z0-9])', t):
                if m.group(1) not in ids:
                    errs.append(f'{f.stem} 文字里的联锁 {m.group(1)} 不在模型里：{t[:30].strip()}…')
    # 4. 回路：按模型 loops[]（测量 / 控制功能 / 最终元件 / 信号类别）核对各环节确实存在；
    #    continuous 模式且没有 loops 时保留旧的 FIC→PCV/PI/XV 同号提示
    names = {'measure': '测量', 'control': '控制功能', 'final': '最终元件'}
    for lp in M.get('loops', []):
        for role in ('measure', 'control', 'final'):
            ref = lp.get(role)
            if ref and ref not in tags:
                errs.append(f'回路 {lp.get("id")} 的{names[role]} {ref} 不在模型里')
    if not stable and not M.get('loops'):
        for t in sorted(tags):
            m = re.match(r'FIC-(\d{3})$', t or '')
            if m:
                n = m.group(1)
                for pre in ('PCV', 'PI', 'XV'):
                    if f'{pre}-{n}' not in tags:
                        warns.append(f'FIC-{n} 没有同号的 {pre}-{n}')
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('WARN ', w)
    print('NUMBERING', 'PASS' if not errs else f'FAIL {len(errs)}', 'warn', len(warns), f'模式 {mode}')
    return not errs


if __name__ == '__main__':
    argv = sys.argv[1:]
    prof = argv[argv.index('--profile') + 1] if '--profile' in argv else None
    sys.exit(0 if main(argv[0], argv[1], prof) else 1)
