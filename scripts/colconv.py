"""联锁表、工况表的列定义：make_review.py 和 make_ce_modes.py 共用，避免两处各读各的格式。

模型里 conventions 可以这样写（两种都认）：
  action_columns  [[键, 表头, 简称], …]  或  [[键, 表头], …]  或  [键, …]（表头取 action_names[键]，缺省用键名）
  mode_columns    [[键, 表头], …]        或  [键, …]（表头取 mode_names[键]，缺省用键名）
没写（或写成空表）时，按联锁和工况里实际出现的键生成，表头用键名；不再带入别的项目的列头。
"""

import sys

MODE_FIXED = ('id', 'name', 'permissive', 'exit')


def _warn(what, keys):
    if keys:
        print(f'提示：模型没有写 conventions.{what}，列头暂用键名（{"、".join(map(str, keys))}）；要中文列头请在模型里写上。', file=sys.stderr)


def _pairs(items, names, with_short):
    out = []
    for it in items:
        if isinstance(it, str):
            key, head, short = it, names.get(it, it), names.get(it, it)
        else:
            key = it[0]
            head = it[1] if len(it) > 1 else names.get(key, key)
            short = it[2] if len(it) > 2 else head
        out.append([key, head, short] if with_short else [key, head])
    return out


def action_columns(model):
    """返回 [[键, 表头, 简称], …]"""
    conv = model.get('conventions', {})
    items = conv.get('action_columns')
    if not items:
        seen = []
        for il in model.get('interlocks', []):
            for k in il.get('actions', {}):
                if k not in seen:
                    seen.append(k)
        items = seen
        _warn('action_columns', [k for k in items if k not in conv.get('action_names', {})])
    return _pairs(items, conv.get('action_names', {}), True)


def mode_columns(model):
    """返回 [[键, 表头], …]，许可条件、转出条件放最后。"""
    conv = model.get('conventions', {})
    items = conv.get('mode_columns')
    if not items:
        seen = []
        for m in model.get('modes', []):
            for k in m:
                if k not in MODE_FIXED and k not in seen:
                    seen.append(k)
        items = seen
        _warn('mode_columns', [k for k in items if k not in conv.get('mode_names', {})])
    cols = _pairs(items, conv.get('mode_names', {}), False)
    keys = [c[0] for c in cols]
    if model.get('modes') or 'permissive' in keys:
        for k, h in (('permissive', '许可条件'), ('exit', '转出条件')):
            if k not in keys:
                cols.append([k, h])
    return cols
