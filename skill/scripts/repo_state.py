#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一屏现状 —— 动线①的开场动作，替代「读 4 份头注 + ls 两个归档目录 + 调 Release API」。

为什么存在：
    「现在是什么状态」在仓里没有单一落点：版本号只写在 4 个现役文件的头注里、
    归档进度要看两个 config_old 目录、最新 Release / CI 结论要调 GitHub。
    AI 每个任务开工都要花 4-6 次工具调用摸底 —— 本脚本一次输出全部。
    它是**只读实时计算**，不维护任何状态文件（维护态文件必然漂移）。

用法：
    python skill/scripts/repo_state.py          # 人读表格（默认）
    python skill/scripts/repo_state.py --json   # 机读 JSON
"""

import json
import os
import re
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACTIVE = {
    ('surge', 'lazy'): 'surge/profiles/lazy.conf',
    ('surge', 'routing'): 'surge/profiles/routing.conf',
    ('egern', 'lazy'): 'egern/profiles/lazy.yaml',
    ('egern', 'routing'): 'egern/profiles/routing.yaml',
}
VER_RE = re.compile(r'#!\s*version=(\S+)')
ARCH_RE = re.compile(r'_(v\d+(?:\.\d+){0,2})\.(?:conf|yaml)$')


def _git(*args):
    r = subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.stdout.strip() if r.returncode == 0 else None


def _gh(*args):
    try:
        r = subprocess.run(['gh', *args], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def collect():
    state = {'active_versions': {}, 'next_suggested': {}, 'archive_latest': {},
             'release': None, 'ci': None}

    # ① 四份现役头注版本号
    for (kern, fam), rel in ACTIVE.items():
        p = os.path.join(ROOT, rel)
        m = VER_RE.match(open(p, encoding='utf-8').readline()) if os.path.exists(p) else None
        # 头注值形如 lazy_v1.9 —— 剥掉产品线前缀，统一显示 v1.9
        state['active_versions'][f'{kern}-{fam}'] = m.group(1).split('_', 1)[-1] if m else None
    # ①-b 建议下一位版本号（三段制默认小修 +Z；与现役同键名）
    state['next_suggested'] = {k: _next_minor(v) for k, v in state['active_versions'].items() if v}

    # ② 归档进度：config_old 每个产品线的最新归档号
    for kern in ('surge', 'egern'):
        d = os.path.join(ROOT, kern, 'profiles', 'config_old')
        best = {}
        if os.path.isdir(d):
            for fn in os.listdir(d):
                m = ARCH_RE.search(fn)
                if m:
                    fam = fn.split('_')[0]
                    if fam not in best or _vkey(m.group(1)) > _vkey(best[fam]):
                        best[fam] = m.group(1)
        state['archive_latest'] |= {f'{kern}-{k}': v for k, v in best.items()}

    # ③ 最新 Release（gh 可用才查；失败给 None，不算错——离线环境是常态）
    remote = _git('remote', 'get-url', 'origin') or ''
    m = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote)
    if m:
        rel = _gh('api', f'repos/{m.group(1)}/releases/latest',
                  '--jq', '{tag: .tag_name, name: .name, published: .published_at}')
        state['release'] = json.loads(rel) if rel else None

    # ④ CI 最新结论
    ci = _gh('run', 'list', '--limit', '1', '--json', 'status,conclusion,displayTitle',
             '--jq', '.[0]')
    state['ci'] = json.loads(ci) if ci else None
    return state


def _vkey(v):
    return tuple(int(x) for x in v[1:].split('.'))


def _next_minor(v):
    """建议下一位版本号（三段制，默认小修 = Z 位 +1）：v2.0 → v2.0.1 · v2.0.1 → v2.0.2。
    中改（Y+1）/大改（X+1）由人定档，本函数只给默认值防心算出错。"""
    parts = [int(x) for x in v[1:].split('.')]
    if len(parts) < 3:
        parts.append(1)
    else:
        parts[-1] += 1
    return 'v' + '.'.join(str(x) for x in parts)


def render(state):
    a = state['active_versions']
    print('══ 现役版本（四份必须同号：lazy 两份一组、routing 两份一组）══')
    print(f"  surge  lazy    {a.get('surge-lazy')}    │ surge  routing  {a.get('surge-routing')}")
    print(f"  egern  lazy    {a.get('egern-lazy')}    │ egern  routing  {a.get('egern-routing')}")
    ns = state.get('next_suggested', {})
    print('══ 建议下一位（三段制默认小修 +Z；中改进 Y / 大改进 X 由人定档）══')
    print(f"  surge  lazy    {ns.get('surge-lazy', '-')}    │ surge  routing  {ns.get('surge-routing', '-')}")
    print(f"  egern  lazy    {ns.get('egern-lazy', '-')}    │ egern  routing  {ns.get('egern-routing', '-')}")
    ar = state['archive_latest']
    print('══ 归档进度（config_old 内各产品线最新号；现役 = 归档号的下一位，三段制 X.Y.Z）══')
    for k in ('surge-lazy', 'surge-routing', 'egern-lazy', 'egern-routing'):
        print(f'  {k:<15} {ar.get(k, "-")}')
    r = state['release']
    print('══ 发布层 ══')
    if r:
        print(f"  最新 Release：{r['tag']}　{r['name']}　({r['published'][:10]})")
    else:
        print('  最新 Release：未知（gh 不可用或未发布）')
    c = state['ci']
    if c:
        print(f"  CI：{c.get('status')} / {c.get('conclusion') or '-'}　{c.get('displayTitle', '')[:44]}")
    print('══ 提示 ══')
    print('  闸门验证跑 python skill/tests/verify_all.py（一键、与 CI 同源）；本脚本只报现状，不做验证。')


def main():
    state = collect()
    if '--json' in sys.argv:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        render(state)


if __name__ == '__main__':
    main()
