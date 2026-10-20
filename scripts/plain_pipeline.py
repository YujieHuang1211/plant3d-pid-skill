"""普通图元模式一条龙：版面 → 检查 → 转换 → 预览 → 出图 → 收尾。
用法: python plain_pipeline.py <工作底稿目录> <子命令> [参数]

子命令
  prep   [图号 …]      离线（不需要 AutoCAD，数秒）：运行 sheets.py 生成 Plant 版 spec → lint → plain_convert →
                       lint 普通版 → check_plain → 预览 PNG（<工作底稿>/预览/）。任何一步失败都退出码 1
  draw   [图号 …] [--redraw] [--wait]
                       写 run_set.ps1（带 BOM）并用 Windows PowerShell 5 启动：项目不存在先 setup_project，再
                       build_set -Plain。默认后台运行，日志在 <工作底稿>/_出图日志/；--wait 等它结束。
                       已出过的图要重画，加 --redraw（先移除旧图再画）。draw 之前会再跑一遍 prep 的检查部分
  status               看最近一次出图记录（_出图日志/run_*.json）：退出码 0 完成 / 1 失败或无记录 / 2 运行中或已中断
  post                 出图后：PDF 转 PNG（<工作底稿>/终审PNG/）→ 清空 PDF 元数据 → 合并图集 → 扫描 PDF/DWG 里的
                       禁用词和作者信息 → 打项目 zip 备份。先核对产物（DWG 齐全、单张 PDF 恰 1 页 A3、不早于本次出图），
                       不通过即中止。结果打印；不复制到交付目录（由人确认后再复制）

工作底稿目录里放 pipeline.json（new_project.py 生成），字段：
  profile      制图配置名（assets/profiles/*.json）；缺省 legacy-2026-10，new_project.py 对新项目写 pip-ref-a3
  profile_overrides / profile_override_note
               对制图配置的项目级覆盖（如 {"psv_upright": ["P&ID-107"]}）及理由；合并结果写入 _profile_effective.json
  views        "warn" 时模型核对（validate_views）只列问题不挡出图（老项目补录期间用），缺省为必须通过
  project      Plant 项目名，也是 DWG 标题栏项目名（不得带“验证”“测试”等字样）
  parent       Plant 项目的父目录，默认 E:\\05p_id图绘制中心
  layout       版面模块，默认 sheets.py（用法 python sheets.py <specs 目录> [图号…]）
  catalogs     额外符号目录（相对工作底稿目录或绝对路径），例如本项目的自定义符号
  stylecfg / schema / projprops   新建项目时用的配置，缺省用引擎 specs 目录里的 qmz_* 默认配置和 projprops.json
  dwg          {图号: DWG 文件名}，缺省 “图号_图名.dwg”
  ban          额外禁用词
Plant 版 spec 与普通版 spec 放在 <引擎>/specs/<project> 与 <引擎>/specs/<project>_plain。
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = Path(r'E:\05p_id图绘制中心\_PidBot')
PY = sys.executable
ENC = {'PYTHONIOENCODING': 'utf-8'}


def load(work):
    work = Path(work).resolve()
    cfg = json.loads((work / 'pipeline.json').read_text(encoding='utf-8'))
    cfg['work'] = work
    cfg['stage'] = work.parent
    cfg.setdefault('parent', r'E:\05p_id图绘制中心')
    cfg.setdefault('layout', 'sheets.py')
    cfg.setdefault('profile', 'legacy-2026-10')     # 老项目缺省沿用旧图面；new_project.py 对新项目写 pip-ref-a3
    if cfg.get('profile_overrides'):                # 项目对配置的明确偏离：合并后写成文件，各脚本按路径载入
        import drawprofile
        cfg['profile'] = drawprofile.effective(cfg['profile'], cfg['profile_overrides'], work / '_profile_effective.json',
                                               cfg.get('profile_override_note', ''))
    cfg['specs'] = ENGINE / 'specs' / cfg['project']
    cfg['plain'] = ENGINE / 'specs' / (cfg['project'] + '_plain')
    cfg['catalogs'] = [str(p if Path(p).is_absolute() else work / p) for p in cfg.get('catalogs', [])]
    cfg['model'] = json.loads((work / 'pid_model.json').read_text(encoding='utf-8'))
    cfg['pdf'] = cfg['stage'] / '原生PDF'
    cfg['backup'] = cfg['stage'] / '_恢复备份'
    cfg['prj'] = Path(cfg['parent']) / cfg['project']
    return cfg


def sheets_of(cfg, picked):
    nos = [s['no'] for s in cfg['model']['sheets']]
    for n in picked:
        if n not in nos:
            raise SystemExit(f'没有这张图：{n}；model.sheets 有 {nos}')
    return picked or nos


def dwg_name(cfg, no):
    d = cfg.get('dwg', {})
    if no in d:
        return d[no]
    title = {s['no']: s['title'] for s in cfg['model']['sheets']}[no]
    return re.sub(r'[\\/:*?"<>|\s]', '', f'{no}_{title}') + '.dwg'


def run(cmd, **kw):
    env = dict(os.environ, **ENC)
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, **kw)


def step(name, r, show=6):
    out = (r.stdout + r.stderr).strip().splitlines()
    ok = r.returncode == 0
    print(('OK   ' if ok else 'FAIL ') + name)
    for ln in out[-show:] if ok else out[-25:]:
        print('     ' + ln)
    return ok


def check_phase(cfg, nos, preview=True):
    cat = []
    for c in [HERE.parent / 'assets' / 'symbol_catalog.json'] + [Path(x) for x in cfg['catalogs']]:
        cat += ['--catalog', c]
    cat_plant = []
    for c in cfg['catalogs']:
        cat_plant += ['--catalog', c]
    ok = True
    # 1. 生成 Plant 版 spec
    r = run([PY, cfg['work'] / cfg['layout'], cfg['specs']] + nos, cwd=cfg['work'])
    ok &= step('版面 → Plant 版 spec', r, 2)
    if not ok:
        return False
    # 2. lint（Plant 版：线端几何、压框、文字重叠、id 唯一）
    lcat = cat_plant
    prof = ['--profile', cfg.get('profile', 'legacy-2026-10')]
    r = run([PY, HERE / 'lint_specs.py', cfg['specs']] + nos + lcat + prof)
    ok &= step('lint（Plant 版 spec）', r)
    # 3. 转换
    r = run([PY, HERE / 'plain_convert.py', cfg['specs'], cfg['plain']] + cat + prof + nos)
    ok &= step('plain_convert', r, 2)
    # 4. lint 普通版
    acc = cfg['work'] / 'accepted_warnings.json'
    r = run([PY, HERE / 'lint_specs.py', cfg['plain']] + nos + lcat + prof + ['--block', 'W-TEXT-TEXT,W-TEXT-SYM', '--accept', acc])
    ok &= step('lint（普通版 spec）', r)
    # 5. 内容核查
    ban = ['--ban', ','.join(cfg['ban'])] if cfg.get('ban') else []
    r = run([PY, HERE / 'check_plain.py', cfg['specs'], cfg['plain']] + ban)
    ok &= step('check_plain（位号/线号齐全、唯一、禁用词）', r)
    r = run([PY, HERE / 'check_numbering.py', cfg['work'] / 'pid_model.json', cfg['plain']] + prof)
    ok &= step('check_numbering（线号分组连续、联锁编号连续、文字里的位号都在模型里）', r)
    if set(nos) >= {s['no'] for s in cfg['model']['sheets']}:       # 覆盖核对要看整套图；只跑子集时跳过
        r = run([PY, HERE / 'validate_views.py', cfg['work'] / 'pid_model.json', cfg['specs'], cfg['plain']]
                + (['--warn-only'] if cfg.get('views') == 'warn' else []))
        ok &= step('validate_views（模型对象与连接都画进图、位号贴在对象旁、跨图成对）', r)
    else:
        print('SKIP validate_views（只处理了部分图，整套 prep 时才核对覆盖）')
    if preview and ok:
        pv = cfg['work'] / '预览'
        r = run([PY, HERE / 'preview_spec.py', cfg['plain'], pv] + nos + cat + prof + ['--scale', '3'])
        ok &= step(f'预览 → {pv}', r, 1)
    return bool(ok)


def ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def write_run_script(cfg, nos, redraw):
    sheets = ';'.join(f'{n}|{dwg_name(cfg, n)}' for n in nos)
    sc = ENGINE / 'scripts'
    lines = ["$ErrorActionPreference = 'Stop'", "$env:PYTHONIOENCODING = 'utf-8'",
             "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); $OutputEncoding = [Console]::OutputEncoding"]
    if not (cfg['prj'] / 'Project.xml').exists():
        pp = cfg.get('projprops') or str(cfg['work'] / 'projprops.json')
        cmd = f"& {ps_quote(sc / 'setup_project.ps1')} -Name {ps_quote(cfg['project'])} -Parent {ps_quote(cfg['parent'])} -ProjProps {ps_quote(pp)}"
        if cfg.get('stylecfg'):
            cmd += f" -StyleCfg {ps_quote(cfg['stylecfg'])}"
        if cfg.get('schema'):
            cmd += f" -Schema {ps_quote(cfg['schema'])}"
        lines.append(cmd)
    cmd = (f"& {ps_quote(sc / 'build_set.ps1')} -Project {ps_quote(cfg['prj'] / 'Project.xml')} -Specs {ps_quote(cfg['plain'])} "
           f"-Pdf {ps_quote(cfg['pdf'])} -Backup {ps_quote(cfg['backup'])} -Sheets {ps_quote(sheets)} -Plain")
    if cfg.get('stylecfg'):
        cmd += f" -StyleCfg {ps_quote(cfg['stylecfg'])}"
    if redraw:
        cmd += ' -Redraw'
    lines.append(cmd)
    p = cfg['work'] / 'run_set.ps1'
    p.write_bytes(b'\xef\xbb\xbf' + '\r\n'.join(lines).encode('utf-8'))     # 带 BOM，Windows PowerShell 5 才能读中文路径
    return p


def acad_running():
    """有线程的 acad 进程（已死但句柄残留的僵尸进程线程数为 0，不算）"""
    r = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                        "Get-Process acad -ErrorAction SilentlyContinue | Where-Object { $_.Threads.Count -gt 0 } | ForEach-Object { $_.Id }"],
                       capture_output=True, text=True, errors='replace')
    return [x.strip() for x in r.stdout.splitlines() if x.strip().isdigit()]


# ---------------------------------------------------------------- 运行记录（出图成败只认记录，不认日志里的字样）
def log_dir(cfg):
    d = cfg['work'] / '_出图日志'
    d.mkdir(exist_ok=True)
    return d


def write_record(cfg, rec):
    """合并写入 _出图日志/run_<编号>.json"""
    f = log_dir(cfg) / f"run_{rec['run_id']}.json"
    old = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    old.update(rec)
    f.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf-8')
    return old


def pid_alive(pid):
    if not pid:
        return False
    if os.name == 'nt':
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))       # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259            # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def latest_record(cfg):
    """最近一次出图记录；记录写着 running 而进程已不在，改记为 interrupted"""
    d = cfg['work'] / '_出图日志'
    fs = sorted(d.glob('run_*.json')) if d.exists() else []
    if not fs:
        return None
    rec = json.loads(fs[-1].read_text(encoding='utf-8'))
    if rec.get('state') == 'running':
        young = not rec.get('pid') and time.time() - rec.get('started', 0) < 30      # 包装进程刚启动，还没登记 PID
        if not young and not pid_alive(rec.get('pid')):
            rec = write_record(cfg, {'run_id': rec['run_id'], 'state': 'interrupted', 'finished': time.time()})
    return rec


def decode_log(b):
    """日志统一写 UTF-8；旧日志是 GBK，先试 UTF-8 再回退"""
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


def verify_outputs(cfg, nos, since=None, need_dwg=True):
    """目标图张的产物核对：DWG 在、单张 PDF 恰 1 页且为 A3 横向、都不早于本次出图开始。返回问题列表"""
    import fitz
    import drawprofile
    S = drawprofile.sheet(drawprofile.load(cfg.get('profile')))
    want = (round(S['width']), round(S['height']))
    bad = []
    for n in nos:
        files = [(cfg['pdf'] / f'{n}.pdf', 'PDF')]
        if need_dwg:
            files.insert(0, (cfg['prj'] / 'PID DWG' / dwg_name(cfg, n), 'DWG'))
        for f, kind in files:
            if not f.exists():
                bad.append(f'{n}: 缺 {kind} {f.name}')
                continue
            if since and f.stat().st_mtime < since:
                bad.append(f'{n}: {kind} {f.name} 早于本次出图开始，疑为旧文件')
            if kind == 'PDF':
                with fitz.open(f) as d:
                    if d.page_count != 1:
                        bad.append(f'{n}: PDF 有 {d.page_count} 页，应为 1 页')
                    elif (round(d[0].rect.width / 72 * 25.4), round(d[0].rect.height / 72 * 25.4)) != want:
                        bad.append(f'{n}: PDF 图幅不是 {S["name"]}（{want[0]}×{want[1]}）')
    return bad


def cmd_draw(cfg, argv):
    redraw = '--redraw' in argv
    wait = '--wait' in argv
    nos = sheets_of(cfg, [a for a in argv if not a.startswith('--')])
    if not check_phase(cfg, sheets_of(cfg, []), preview=False):
        raise SystemExit('检查未通过，未启动 AutoCAD')
    pids = acad_running()
    if pids:
        raise SystemExit(f'已有 AutoCAD 在运行（PID {", ".join(pids)}）。请先保存关闭；引擎不会动不属于它的 AutoCAD')
    exists = [n for n in nos if (cfg['prj'] / 'PID DWG' / dwg_name(cfg, n)).exists()]
    if exists and not redraw:
        raise SystemExit(f'这些图已在项目里：{exists}。重画请加 --redraw')
    script = write_run_script(cfg, nos, redraw)
    run_id = time.strftime('%m%d_%H%M%S')
    log = log_dir(cfg) / f'draw_{run_id}.log'
    write_record(cfg, {'run_id': run_id, 'state': 'running', 'started': time.time(), 'sheets': nos, 'redraw': redraw,
                       'script': str(script), 'log': str(log), 'pid': None})
    flags = 0x08000000 | 0x00000200      # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP（DETACHED_PROCESS 会丢掉输出）
    pr = subprocess.Popen([PY, str(Path(__file__).resolve()), str(cfg['work']), '_runner', run_id],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    print(f'已启动（运行 {run_id}，PID {pr.pid}），日志 {log}')
    print('整套 6 张约 5~6 分钟（含启动）。期间不要打开 AutoCAD。用 status 看进度。')
    if wait:
        pr.wait()
        return show_status(cfg)
    return True


def cmd_runner(cfg, run_id):
    """后台包装进程：启动 PowerShell 出图，等它结束，按返回码和产物核对写最终状态"""
    rec = json.loads((log_dir(cfg) / f'run_{run_id}.json').read_text(encoding='utf-8'))
    write_record(cfg, {'run_id': run_id, 'pid': os.getpid()})
    rc, problems = -1, []
    try:
        with open(rec['log'], 'wb') as f:
            rc = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', rec['script']],
                                stdout=f, stderr=subprocess.STDOUT).returncode
        if rc == 0:
            problems = verify_outputs(cfg, rec['sheets'], since=rec['started'] - 2)
    except Exception as e:
        problems = [f'包装进程异常：{e}']
    state = 'ok' if rc == 0 and not problems else 'failed'
    write_record(cfg, {'run_id': run_id, 'state': state, 'returncode': rc, 'problems': problems, 'finished': time.time()})
    return 0 if state == 'ok' else 1


def status_code(cfg):
    """0 完成；1 失败或没有记录；2 运行中或已中断。只看运行记录，日志只用来展示"""
    rec = latest_record(cfg)
    if not rec:
        print('还没有出图记录')
        return 1
    st = rec.get('state')
    lg = Path(rec['log']) if rec.get('log') else None
    if lg and lg.exists():
        t = decode_log(lg.read_bytes())
        lines = [ln for ln in t.splitlines() if re.search(r'项目配置完成|===|已画完|!!|错误|超时|全部完成|失败|异常', ln)]
        print(lg)
        print('\n'.join(ln[:150] for ln in lines[-30:]))
    for p in rec.get('problems', []):
        print('问题:', p)
    label = {'ok': '全部完成', 'failed': f"失败（返回码 {rec.get('returncode')}），见上", 'running': '进行中',
             'interrupted': '已中断（进程已不在，未见完成记录）'}.get(st, st)
    print(f"结果：{label}（运行 {rec.get('run_id')}）")
    return {'ok': 0, 'failed': 1, 'running': 2, 'interrupted': 2}.get(st, 1)


def show_status(cfg):
    return status_code(cfg) == 0


def scan_text(blob, words):
    return [w for w in words if re.search(r'(?<![A-Za-z0-9])' + re.escape(w) + r'(?![A-Za-z0-9])', blob)] if blob else []


def cmd_post(cfg, argv):
    import fitz
    nos = sheets_of(cfg, [a for a in argv if not a.startswith('--')])
    # 产物核对先于一切收尾：DWG 齐全；单张 PDF 恰 1 页、A3 横向；有成功的出图记录时都须晚于那次出图开始（旧文件不得混入）
    rec = latest_record(cfg)
    since = None
    if rec and rec.get('state') == 'ok' and rec.get('started') and set(nos) <= set(rec.get('sheets', [])):
        since = rec['started'] - 2
    problems = verify_outputs(cfg, nos, since=since)
    if rec and rec.get('state') in ('failed', 'interrupted', 'running'):
        problems.insert(0, f"最近一次出图（{rec.get('run_id')}）状态为 {rec.get('state')}，不得收尾发布")
    if problems:
        for p in problems:
            print('FAIL', p)
        print('收尾中止：产物核对未通过，未合并图集、未备份')
        return False
    png = cfg['work'] / '终审PNG'
    png.mkdir(exist_ok=True)
    for f in png.glob('*.png'):
        f.unlink()
    ok = step('PDF → PNG', run([PY, HERE / 'render_pdfs.py', cfg['pdf'], png]), 1)
    ok &= step('清空 PDF 元数据', run([PY, HERE / 'clean_pdf_meta.py', cfg['work'] / 'pid_model.json', cfg['pdf']]), 1)
    atlas = cfg['stage'] / f"{cfg['project']}_P&ID图集_{cfg['model']['meta'].get('rev', 'R0')}.pdf"
    ok &= step('合并图集', run([PY, HERE / 'pack_pdfs.py', cfg['work'] / 'pid_model.json', cfg['pdf'], atlas, cfg.get('profile', 'legacy-2026-10')]), 1)
    # 扫描元数据与 DWG 里的敏感信息
    bad = ['Claude', 'Codex', 'GPT', 'Anthropic', 'OpenAI', 'PidBot', '验证', '测试']
    for f in [atlas] + [cfg['pdf'] / f'{n}.pdf' for n in nos]:
        m = fitz.open(f).metadata
        extra = [k for k in ('author', 'creator', 'producer', 'subject', 'keywords') if m.get(k)]
        hits = scan_text(' '.join(str(v) for v in m.values()), bad)
        if extra or hits:
            print(f'FAIL PDF 元数据 {Path(f).name}: {extra} {hits}')
            ok = False
    dwgdir = cfg['prj'] / 'PID DWG'
    for n in nos:
        f = dwgdir / dwg_name(cfg, n)
        b = f.read_bytes()
        # 二进制里短词会碰巧出现，只扫 5 个字符以上的词
        hits = [w for w in bad if len(w) >= 5 and (w.encode('utf-8') in b or w.encode('utf-16le') in b)]
        who = set()
        key16 = '<prop id="8"><string>'.encode('utf-16le')
        k = b.find(key16)
        while k >= 0:
            e = b.find('</string>'.encode('utf-16le'), k)
            who.add(b[k + len(key16):e].decode('utf-16le', 'replace'))
            k = b.find(key16, k + 2)
        for m in re.findall(rb'<prop id="8"><string>([^<]*)</string>', b):
            who.add(m.decode('latin1'))
        print(('FAIL ' if hits else 'OK   ') + f'DWG {f.name}: 敏感词 {hits or "无"}；最后保存者 {sorted(who) or "无"}（仅供参考）')
        ok &= not hits
    # 项目 zip（排除 .bak 与锁文件，放在项目外）
    import zipfile
    cfg['backup'].mkdir(exist_ok=True)
    z = cfg['backup'] / f"正式项目_{cfg['model']['meta'].get('rev', 'R0')}_{time.strftime('%Y%m%d')}.zip"
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for r, d, fs in os.walk(cfg['prj']):
            for fn in fs:
                if fn.endswith(('.dwl', '.dwl2', '.bak')):
                    continue
                p = Path(r) / fn
                zf.write(p, p.relative_to(cfg['prj']))
    print('OK   项目备份', z, z.stat().st_size // 1024, 'KB')
    print('逐张看', png, '；确认后再复制到交付目录')
    return ok


def main(argv):
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding='utf-8')
        except Exception:
            pass
    if len(argv) < 2:
        print(__doc__)
        return 1
    cfg = load(argv[0])
    sub, rest = argv[1], argv[2:]
    if sub == 'prep':
        return 0 if check_phase(cfg, sheets_of(cfg, [a for a in rest if not a.startswith('--')])) else 1
    if sub == 'draw':
        return 0 if cmd_draw(cfg, rest) else 1
    if sub == 'status':
        return status_code(cfg)
    if sub == '_runner':
        return cmd_runner(cfg, rest[0])
    if sub == 'post':
        return 0 if cmd_post(cfg, rest) else 1
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
